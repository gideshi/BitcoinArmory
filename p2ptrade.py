from armoryengine import *
import os
import colortools
import json
import urllib, httplib
import threading, time

def make_random_id():
    bits = os.urandom(8)
    return binary_to_hex(bits)

def colorInd(o): return colortools.find_color_index(o['colorid'])

standard_offer_expiry_interval = 60 * 2
standard_offer_grace_interval = 20

class ExchangeOffer(object): 
    # A = offerer's side, B = replyer's side
    # ie. offerer says "I want to give you A['value'] coins of color 
    # A['colorid'] and receive B['value'] coins of color B['colorid']"
    def __init__(self, oid, A, B):
        self.oid = oid or make_random_id()
        self.A = A
        self.B = B
        self.expires = None

    def expired(self, shift = 0):
        return (not self.expires) or (self.expires < time.time() + shift)

    def refresh(self, delta = standard_offer_expiry_interval):
        self.expires = time.time() + delta

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
            return True

        if not checkprop('colorid'):  return False
        if not checkprop('value'): return False
        return True

    @classmethod
    def importTheirs(cls, data):
        # TODO: verification
        return ExchangeOffer(data["oid"], data["A"], data["B"])

class MyExchangeOffer(ExchangeOffer):
    def __init__(self, oid, A, B, auto_post=True):
        super(MyExchangeOffer, self).__init__(oid, A, B)
        self.auto_post = auto_post

class MyTranche(object):
    @classmethod
    def createPayment(cls, wallet, color, amount, to_address160):
        p = MyTranche()
        p.txdp = None
        p.utxoList = wallet.getTxOutListX(color, 'Spendable')
        p.utxoSelect = PySelectCoins(p.utxoList, amount, 0)
        if p.utxoSelect:
            totalSelectCoins = sum([u.getValue() for u in p.utxoSelect])
            change = totalSelectCoins - amount
            p.recipientPairs   = [[to_address160, amount]]
            if change > 0:
                addr = p.utxoSelect[0].getRecipientAddr()
                # TODO: check invalid addr?
                p.recipientPairs.append([addr, change])
            return p
        else:
            raise Exception("not enough money(?)")

    def makeTxDistProposal(self):
        txdp = PyTxDistProposal()
        txdp.createFromTxOutSelection(self.utxoSelect, self.recipientPairs)
        return txdp


def merge_txdps(l, r):
    res = l.pytxObj.copy()
    rtx = r.pytxObj
    res.inputs += rtx.inputs
    res.outputs += rtx.outputs
    res.isSigned = False
    res.lockTime = 0
    res.thisHash = res.getHash()
    p = PyTxDistProposal()
    p.createFromPyTx(res)
    return p
    

class ExchangeTransaction:
    def __init__(self):
        self.txdp = None

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
        finalTx.pprint()
        engine_broadcast_transaction(finalTx)

    def getASCIITxDP(self):
        return self.getTxDP().serializeAscii()

class ExchangeProposal:
    def createNew(self, offer, my_tranche, my_offer):
        self.pid = make_random_id()
        self.offer = offer
        self.my_tranche = my_tranche
        self.etransaction = ExchangeTransaction()
        self.etransaction.addMyTranche(self.my_tranche)
        self.my_offer = my_offer
        self.state = 'proposed'

    def export(self):
        return {"pid": self.pid,
                "offer": self.offer.export(),
                "txdp": self.etransaction.getASCIITxDP()}

    def importTheirs(self, data):
        self.pid = data["pid"]
        self.offer = ExchangeOffer.importTheirs(data["offer"])
        self.etransaction = ExchangeTransaction()
        txdp = PyTxDistProposal()
        txdp.unserializeAscii(data['txdp'])
        self.etransaction.addTxDP(txdp)
        self.my_tranche = None
        self.my_offer = None
        self.state = 'imported'

    def addMyTranche(self, my_tranche):
        self.my_tranche = my_tranche
        self.etransaction.addMyTranche(my_tranche)

    # Does their tranche have enough of the color
    # that I want going to my address?
    def checkOutputsToMe(self,myaddress,color,value):
        txdp = self.etransaction.getTxDP()
        coloredOutputs = colortools.compute_pytx_colors(txdp.pytxObj)
        print coloredOutputs
        sumv = 0
        for out,col in zip(txdp.pytxObj.outputs,coloredOutputs):
          if TxOutScriptExtractAddr160(out.binScript) == myaddress:
            if col == color:
              sumv += out.value
        offer = self.offer
        return sumv >= value

    # Are all of the inputs in my tranche?
    def checkInputsFromMe(self,wallet): # TODO: it doesn't work 
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
        
    def signMyTranche(self, wallet):
        if self.checkInputsFromMe(wallet): # nope nope nope
            wallet.signTxDistProposal(self.etransaction.txdp)
        else:
            raise Exception, "signMyTranche: won't sign because inputs from my wallet are not in tranche"

class ExchangePeerAgent:
    def __init__(self, wallet, comm):
        self.my_offers = dict()
        self.their_offers = dict()
        self.wallet = wallet
        self.active_ep = None
        self.ep_timeout = None
        self.comm = comm
        self.match_orders = False

    def setActiveEP(self, ep):
        if ep == None:
            self.ep_timeout = None
            self.match_orders = True
        else:
            self.ep_timeout = time.time() + standard_offer_expiry_interval
        self.active_ep = ep

    def hasActiveEP(self):
        if self.ep_timeout and self.ep_timeout < time.time():
            self.setActiveEP(None) # TODO: cleanup?
        return self.active_ep != None

    def serviceMyOffers(self):
        for my_offer in self.my_offers.itervalues():
            if my_offer.auto_post:
                if not my_offer.expired(-standard_offer_grace_interval): continue
                if self.active_ep and self.active_ep.offer.oid == my_offer.oid: continue
                my_offer.refresh()
                self.postMessage(my_offer)
                
    def serviceTheirOffers(self):
        for their_offer in self.their_offers.itervalues():
            if their_offer.expired(+standard_offer_grace_interval):
                del self.their_offers[their_offer.oid]

    def updateState(self):
        if self.match_offers:
            self.match_offers = False
            self.matchOffers()
        self.serviceMyOffers()
        self.serviceTheirOffers()

    def registerMyOffer(self, offer):
        assert isinstance(offer, MyExchangeOffer)
        if not 'address' in offer.A:
            offer.A['address'] = self.wallet.getNextUnusedAddress().getAddr160()
        self.my_offers[offer.oid] = offer
        self.match_offers = True

    def registerTheirOffer(self, offer):
        self.their_offers[offer.oid] = offer
        offer.refresh()
        self.match_offers = True

    def matchOffers(self):
        if self.hasActiveEP():
            return
        for my_offer in self.my_offers.itervalues():
            for their_offer in self.their_offers.itervalues():
                if my_offer.matches(their_offer):
                    success = False
                    try:
                        self.makeExchangeProposal(their_offer, my_offer.A['address'], my_offer.A['value'], my_offer)
                        success = True
                    except Exception as e:
                        print "Exception during matching: %s" % e
                    if success: return

    def makeExchangeProposal(self, orig_offer, my_address, my_value, related_offer):
        if self.hasActiveEP():
            raise Exception, "already have active EP (in makeExchangeProposal"
        offer = ExchangeOffer(orig_offer.oid, orig_offer.A.copy(), orig_offer.B.copy())
        assert my_value == offer.B['value'] # TODO: support for partial fill
        offer.B['address'] = my_address
        acolor, bcolor = colorInd(offer.A), colorInd(offer.B)
        if not acolor or not bcolor:
            raise Exception("My colorid is not recognized")
        my_tranche = MyTranche.createPayment(self.wallet, bcolor, my_value, offer.A['address'])
        ep = ExchangeProposal()
        ep.createNew(offer, my_tranche, related_offer)
        self.setActiveEP(ep)
        self.postMessage(ep)

    def dispatchExchangeProposal(self, ep_data):
        ep = ExchangeProposal()
        ep.importTheirs(ep_data)
        if self.hasActiveEP():
            if ep.pid == self.active_ep.pid:
                if self.active_ep.state == 'proposed':
                    return self.updateExchangeProposal(ep)
                else:
                    return None # it is our own proposal or something like that
        else:
            if ep.offer.oid in self.my_offers:
                return self.acceptExchangeProposal(ep)
        # We have neither an offer nor a proposal matching this ExchangeProposal
        if ep.offer.oid in self.their_offers:
            # remove offer if it is in-work
            # TODO: set flag instead of deleting it
            del self.their_offers[ep.offer.oid]
        return None
        
    def acceptExchangeProposal(self, ep):
        if self.hasActiveEP():
            # TODO: renegotiate?
            return
        offer = ep.offer
        my_offer = self.my_offers[offer.oid]
        if not offer.isSameAsMine(my_offer):
            raise Exception("Is invalid or incongruent with my offer")
        acolor, bcolor = colorInd(offer.A), colorInd(offer.B)
        if not acolor or not bcolor:
            raise Exception("My colorid is not recognized")
        if not ep.checkOutputsToMe(offer.A['address'], bcolor, offer.B['value']):
            raise Exception("Offer does not contain enough coins of the color that I want for me")
        ep.addMyTranche(MyTranche.createPayment(self.wallet, acolor, offer.A['value'], offer.B['address']))
        ep.signMyTranche(self.wallet)
        self.setActiveEP(ep)
        ep.state = 'accepted'
        self.postMessage(ep)

    def clearOrders(self, ep):
        if ep.my_offer:
            del self.my_offers[ep.my_offer.oid]
            del self.their_offers[ep.offer.oid]
        else:
            del self.my_offers[ep.offer.oid]

    def updateExchangeProposal(self, ep):
        my_ep = self.active_ep
        assert my_ep and my_ep.pid == ep.pid
        offer = my_ep.offer
        ep.my_tranche = my_ep.my_tranche
        acolor, bcolor = colorInd(offer.A), colorInd(offer.B)
        if not acolor or not bcolor:
            raise Exception("My colorid is not recognized")
        if not ep.checkOutputsToMe(offer.B['address'], acolor, offer.A['value']): 
            raise Exception("Offer does not contain enough coins of the color that I want for me")
        ep.etransaction.getTxDP().pprint()
        ep.signMyTranche(self.wallet)
        ep.etransaction.getTxDP().pprint()
        if not (ep.etransaction.getTxDP().checkTxHasEnoughSignatures()):
            raise Exception("Not all inputs are signed for some reason")
        ep.etransaction.broadcast()
        self.clearOrders(self.active_ep)
        self.setActiveEP(None)


    def postMessage(self, obj):
        self.comm.postMessage(obj.export())

    def dispatchMessage(self, content):
        if 'oid' in content:
            o = ExchangeOffer(content['oid'],content['A'],content['B'])
            self.registerTheirOffer(o)
        elif 'pid' in content:
            self.dispatchExchangeProposal(content)


class HTTPExchangeComm:
    def __init__(self):
        self.agents = []
        self.lastpoll = 0

    def addAgent(self, agent):
        self.agents.append(agent)

    def postMessage(self, content):
        h = httplib.HTTPConnection('localhost:8080')
        data = json.dumps(content)
        h.request('POST', '/messages', data, {})
        return k.getresponse().read() == 'Success'

    def pollAndDispatch(self):
        h = httplib.HTTPConnection('localhost:8080')
        h.request('GET','/messages?from_serial=%s' % (lastpoll+1),{})
        try:
            resp = json.loads(h.getresponse().read())
            for x in resp:
                if x.get('serial') > lastpoll: lastpoll = x.get('serial')
                content = x.get('content')
                for a in self.agents:
                    a.dispatchMessage(content)
            return True      
        except:
            return False

    def update(self):
        self.pollAndDispatch()
        for a in self.agents:
            a.updateState()

    def startUpdateLoopThread(self):
        def infipoll():
            while 1:
                time.sleep(15)
                self.update()
        t = threading.Thread(target=infipoll)
        t.start()
        return t
