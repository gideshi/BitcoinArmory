from armoryengine import *
import os
import colortools
import json
import urllib, httplib
import threading, time

def make_random_id():
    bits = os.urandom(8)
    return bin_to_hex(bits)

def colorInd(o): return colortools.find_color_index(o['colorid'])

class ExchangeOffer: 
    # A = offerer's side, B = replyer's side
    # ie. offerer says "I want to give you A['value'] coins of color 
    # A['colorid'] and receive B['value'] coins of color B['colorid']"
    def __init__(self, oid, A, B):
        self.oid = oid or make_random_id()
        self.A = A
        self.B = B

    def export(self):
        return {"oid": self.oid,
                "A": self.A,
                "B": self.B}

    def matches(self, offer):
        """A <=x=> B"""
        def prop_matches(name):
            if ((self.A[name] == offer.B[name]) and
                (self.B[name] == offer.A[name])):
                return True
        return prop_matches('value') and prop_matches('colorid')

    def isSameAsMine(self, my_offer):
        # One of addresses is missing in my_offer
        if 'address' in my_offer.A:
            if self.A['address'] != my_offer.A['address']: return False
        if 'address' in my_offer.B:
            if self.B['address'] != my_offer.B['address']: return False

        def checkprop(name):
            if self.A[name] != my_offer.A[name]: return False
            if self.B[name] != my_offer.B[name]: return False

        if not checkprop('colorid'): return False
        if not checkprop('value'): return False

        return True

    @classmethod
    def importTheirs(cls, data):
        # TODO: verification
        return ExchangeOffer(data["oid"], data["A"], data["B"])

class MyTranche(object):
    @classmethod
    def createPayment(cls, wallet, color, amount, to_address160):
        p = MyETransactionTranche()
        p.txdp = None
        p.utxoList = wallet.getTxOutListX(color, 'Spendable')
        p.utxoSelect = PySelectCoins(p.utxoList, amount, 0)
        if p.utxoSelect:
            totalSelectCoins = sum([u.getValue() for u in p.utxoSelect])
            change = totalSelectCoins - amount
            self.recipientPairs   = [[to_address, amount]]
            if change > 0:
                addr = self.utxoSelect[0].getRecipientAddr()
                # TODO: check invalid addr?
                p.recipientPairs.append([addr, change])
        else:
            raise Exception("not enough money(?)")

    def makeTxDistProposal(self):
        txdp = PyTxDistProposal()
        txdp.createFromTxOutSelection(p.utxoSelect, p.recipientPairs)
        return txdp


def merge_txdps(l, r):
    res = l.pytxObj.copy()
    rtx = r.pytxObj
    res.inputs += rtx.inputs
    res.outputs += rtx.outputs
    res.isSigned = False
    res.lockTime = 0
    res.thisHash = res.getHash()
    return res
    

class ExchangeTransaction:
    def __init__(self):
        self.txdp = None
        pass

    def addMyTranche(self, my_tranche):
        self.addTxDP(my_tranche.makeTxDistProposal())

    def addTxDP(self, atxdp):
        if not self.txdp:
            self.txdp = atxdp
        else:
            self.txdp = merge_txdps(self.txdp, atxdp)

    def getTxDP(self):
        assert self.txdp
        return self.txdp

    def broadcast(self):
        finalTx = self.getTxDP().prepareFinalTx()
        engine_broadcast_transaction(finalTx)

    def getASCIITxDP(self):
        return self.getTxDP().serializeAscii()

class ExchangeProposal:
    def createNew(self, offer, my_tranche):
        self.pid = make_random_id()
        self.offer = offer
        self.my_tranche = my_tranche
        self.etransaction = ExchangeTransaction()
        self.etransaction.addMyTranche(self.my_tranche)
        self.sealed = False

    def export(self):
        return {"pid": self.pid,
                "offer": self.offer.export(),
                "txdp": self.etransaction.getASCIITxDP()}

    def importTheirs(self, data):
        self.pid = data["pid"]
        self.offer = ExchangeOffer.importTheirs(data["offer"])
        self.etransaction = ExchangeTransaction()
        txdp = PyTransactionDistProposal()
        txdp.unserializeAscii(data['txdp'])
        self.etransaction.addTxDP(txdp)
        self.my_tranche = None

    def addMyTranche(self, my_tranche):
        self.my_tranche = my_tranche
        self.etransaction.addMyTranche(my_tranche)

    # Does their tranche have enough of the color
    # that I want going to my address?
    def checkOutputsToMe(self,myaddress,color,value):
        txdp = self.etransaction.getTxDP()
        coloredOutputs = colortools.compute_pytx_colors(txdp)
        sumv = 0
        for out,col in zip(txdp.pytxObj.outputs,coloredOutputs):
          if TxOutScriptExtractAddr160(out.binScript) == myaddress:
            if col[1] == color:
              sumv += out.value
        offer = self.offer
        return sumv >= value

    # Are all of the inputs in my tranche?
    def checkInputsFromMe(self,wallet):
        txdp = self.etransaction.getTxDP()
        tranche = self.my_tranche
        for inp in txdp.pytxObj.inputs:
          addr160 = TxInScriptExtractAddr160IfAvail(inp)
          if addr160 and wallet.hasAddr(addr160):
            invalid = True
            for goodInp in tranche.txdp.pytxObj.inputs:
              if inp.outpoint.txHash == goodInp.outpoint.txHash and \
                inp.outpoint.txOutIndex == goodInp.outpoint.txOutIndex:
                  invalid = False
                  break
            if invalid: return False
        return True
        
    def signMyTranche(self,wallet):
        if self.checkInputsFromMe(wallet):
           wallet.signTxDistProposal(self.extransaction.txdp)

class ExchangePeerAgent:
    def __init__(self, wallet):
        self.my_offers = dict()
        self.their_offers = dict()
        self.wallet = wallet
        self.eproposals = dict()
        self.lastpoll = 0
        self.pollingloop()

    def registerMyOffer(self, offer):
        self.my_offers[offer.oid] = offer
        self.matchOffers()

    def registerTheirOffer(self, offer):
        self.their_offers[offer.oid] = offer
        self.matchOffers()

    def matchOffers(self):
        for my_offer in self.my_offers:
            for their_offer in self.their_offers:
                if my_offer.matches(their_offer):
                    self.makeExchangeProposal(their_offer, my_offer.A['address'], my_offer.A['value'])

    def makeExchangeProposal(self, orig_offer, my_address, my_value):
        offer = ExchangeOffer(orig_offer.oid, orig_offer.A.copy(), orig_offer.B.copy())
        assert my_value == offer.B['value'] # TODO: support for partial fill
        offer.B['address'] = my_address
        acolor, bcolor = colorInd(offer.A), colorInd(offer.B)
        if not acolor or not bcolor:
            raise Exception("My colorid is not recognized")
        my_tranche = MyTranche.createPayment(self.wallet, bcolor, my_value, offer.A['address'])
        ep = ExchangeProposal(offer, my_tranche)
        self.eproposals[ep.pid] = ep
        self.postMessage(ep)

    def dispatchExchangeProposal(self, ep_data):
        ep = ExchangeProposal()
        ep.importTheirs(ep_data)
        if ep.offer.oid in self.my_offers:
          return self.acceptExchangeProposal(ep)
        elif ep.offer.pid in self.eproposals:
          return self.updateExchangeProposal(ep)
        else: 
          # We have neither an offer nor a proposal matching this ExchangeProposal
          return None
        
    def acceptExchangeProposal(self, ep):
        if ep.pid in self.eproposals:
            # TODO: renegotiation?
            return # duplicate detected
        offer = ep.offer
        my_offer = self.my_offers[offer.oid]
        if not offer.isSameAsMine(my_offer):
            raise Exception("Is invalid or incongruent with my offer")
        if not ep.checkOutputsToMe(offer.A['address'],offer.B['color'],offer.B['value']):
            raise Exception("Offer does not contain enough coins of the color that I want for me")
        ep.addMyTranche(MyTranche.createPayment(self.wallet, offer.A['color'], offer.A['value'], offer.B['address']))
        ep.signMyTranche(self.wallet)
        self.eproposals[ep.pid] = ep
        self.postMessage(ep)

    def updateExchangeProposal(self, ep):
        my_ep = self.eproposals.get([ep.pid], None)
        if my_ep.sealed:
            # cannot update sealed EP
            return
        offer = my_ep.offer
        ep.my_tranche = my_ep.my_tranche
        if not ep.checkOutputsToMe(offer.B['address'],offer.A['color'],offer.A['value']): 
            raise Exception("Offer does not contain enough coins of the color that I want for me")
        ep.signMyTranche(self.wallet)
        if not (ep.etransaction.getTxDP().checkTxHasEnoughSignatures()):
            raise Exception("Not all inputs are signed for some reason")
        my_ep.sealed = True
        ep.etransaction.broadcast()


    def postMessage(self,obj):
        h = httplib.HTTPConnection('localhost:8080')
        data = json.dumps(obj.export())
        h.request('POST', '/messages', data, {})
        return k.getresponse().read() == 'Success'

    def poll(self):
        h = httplib.HTTPConnection('localhost:8080')
        h.request('GET','/messages?from_serial=%s' % (lastpoll+1),{})
        try:
            resp = json.loads(h.getresponse().read())
            for x in resp:
                if x.get('serial') > lastpoll: lastpoll = x.get('serial')
                content = x.get('content')
                if 'oid' in content:
                    o = ExchangeOffer(content['oid'],content['A'],content['B'])
                    self.registerTheirOffer(o)
                elif 'pid' in content:
                    self.dispatchExchangeProposal(content)
                else:
                    return False
            return True      
        except:
            return False

    def pollingloop(self):
        def infipoll():
            while 1:
                time.sleep(15)
                self.poll()
        t = threading.Thread(target=infipoll)
        t.start()
        return t
