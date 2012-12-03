from armoryengine import *
import os
import colortools
import json

def make_random_id():
    bits = os.urandom(8)
    return bin_to_hex(bits)

def colorInd(o): return colortools.find_color_index(o['colorid'])

class ExchangeOffer: 
    # Offer = "I want to give you A['value'] coins of color A['colorid'] and receive
    # B['value'] coins of color B['colorid']"
    def __init__(self, oid, A, B):
        self.oid = oid or make_random_id()
        self.A = A
        self.B = B

    def export(self):
        return {"oid": self.oid,
                "A": self.A,
                "B": self.B}

    def matchesOffer(self,other):
        if colorInd(self.A) != colorInd(other.B) or \
           colorInd(self.B) != colorInd(other.A): return False
        if self.A['value'] != other.B['value']: return False
        if other.A['value'] < self.B['value']: return False
        return True

    @classmethod
    def importTheirs(cls, data):
        # TODO: verification
        return ExchangeOffer(data.oid, data["A"], data["B"])

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

class TheirETransactionTranche(ETransactionTranche):
    @classmethod
    def importTxDP(cls, txdp_ascii):
        self.txdp = PyTxDistProposal()
        self.txdp.unserializeAscii(txpd_ascii)

        

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

    def getASCIITxDP(self):
        return self.getTxDP().serializeAscii()

class ExchangeProposal:
    def createNew(self, offer, my_tranche):
        self.pid = make_random_id()
        self.offer = offer
        self.my_tranche = my_tranche
        self.etransaction = ExchangeTransaction()
        self.etransaction.addMyTranche(self.my_tranche)

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

    def checkTheirTranche(self):
        txdp = self.etransaction.getTxDP()
        # TODO: look for transactions of the right color and value in txdp
        return True
        

class ExchangePeerAgent:
    def __init__(self, wallet):
        self.offers = dict()
        self.wallet = wallet
        self.eproposals = dict()

    def registerOffer(self, offer):
        self.offers[offer.oid] = offer
    
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
        return ep
        
    def acceptExchangeProposal(self, their_ep_data):
        ep = ExchangeProposal()
        ep.importTheirs(their_ep_data)

        my_ep = self.eproposals.get([ep.pid], None)
        if my_ep:
            # we have matching ep
            return self.updateExchangeProposal(my_ep, ep)

        matching_offer = self.offers[ep.offer.oid]
        if not matching_offer:
            raise Exception("Found no matching order with that ID")
        if not ep.offer.matchesOffer(matching_offer):
            raise Exception("Is incongruent with my offer")
        if not ep.checkTheirTranche():
            raise Exception("Their tranche is erroneous")
        offer = ep.offer
        acolor, bcolor = colorInd(offer.A), colorInd(offer.B)
        if not acolor or not bcolor:
            raise Exception("My colorid is not recognized")
        ep.addMyTranche(MyTranche.createPayment(self.wallet, color, offer.A['value'], offer.B['address']))
        ep.signMyTranche(self.wallet)
        self.eproposals[ep.pid] = ep
        return ep

    def updateExchangeProposal(self, my_ep, their_ep):
        
        ep.signMyTranche(self.wallet)
