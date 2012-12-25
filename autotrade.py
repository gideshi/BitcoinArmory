from armoryengine import *
from collections import defaultdict

def findMatchingAddr(utxo):
    txhash = utxo.getTxHash()
    tx = TheBDM.getTxByHash(txhash)
    txin = tx.getTxIn(0)
    return TheBDM.getSenderAddr20(txin)



class AutoTrade(object):
    def __init__(self, wallet):
        self.wallet = wallet
        
    def initAddresses(self, in_addr, accum_addr, out_addr):
        self.in_addr160 = addrStr_to_hash160(in_addr)
        self.out_addr160 = addrStr_to_hash160(out_addr)
        self.accum_addr160 = addrStr_to_hash160(accum_addr)
        if not self.wallet.hasAddr(self.in_addr160):
            raise Exception("No in_addr in wallet")
        if not self.wallet.hasAddr(self.out_addr160):
            raise Exception("No out_addr in wallet")

    def initConversion(self, in_color, out_color, rate):
        self.in_color = in_color
        self.out_color = out_color
        self.rate = rate

    def register(self, main):
        def ct():
            self.check_and_trade()
        main.extraHeartbeatFunctions.append(ct)

    def check_and_trade(self):
        in_utxoList = self.wallet.getAddrTxOutListX(self.in_color, self.in_addr160, 'Spendable')
        if len(in_utxoList) > 0:
            self.process_incoming_payments(in_utxoList)

    def want_payment(self, utxo, addr, value):
        return True
        # ignore pay-to-self
        return not self.wallet.hasAddr(addr)

    def aggregate_incoming_payments(self, in_utxoList):
        addr_invalue = defaultdict(int)
        addr_utxo = defaultdict(list)
        addr_outvalue = dict()
        for utxo in in_utxoList:
            addr = findMatchingAddr(utxo)
            value = utxo.getValue()
            if self.want_payment(utxo, addr, value):
                addr_invalue[addr] += value
                addr_utxo[addr].append(utxo)
        for addr, value in addr_invalue.iteritems():
            outvalue = int(value * self.rate)
            if outvalue == 0:
                # can't be used
                del addr_utxo[addr]
                del addr_invalue[addr]
            else:
                addr_outvalue[addr] = outvalue
        return addr_invalue, addr_utxo, addr_outvalue

    def make_in_tranche(self, addr_utxo, fee = 0):
        tranche_utxos = []
        total_invalue = 0
        for utxo_list in addr_utxo.values():
            tranche_utxos += utxo_list
            total_invalue += sum([u.getValue() for u in utxo_list])
        if total_invalue < fee:
            raise Exception, "Not enough incoming payments to pay a fee"
        return (tranche_utxos, [[self.accum_addr160, (total_invalue - fee)]])

    def make_out_tranche(self, addr_outvalue, fee = 0):
        recip = []
        total_outvalue = 0
        for addr, outvalue in addr_outvalue.iteritems():
            total_outvalue += outvalue
            recip.append([addr, outvalue])

        out_utxoList = self.wallet.getAddrTxOutListX(self.out_color, self.out_addr160, 'Spendable')
        out_utxoSelect = PySelectCoins(out_utxoList, total_outvalue, fee) if out_utxoList else None
        if not out_utxoSelect:
            raise Exception, "Not enough coins for output, aborting"
        utxo_value = sum([u.getValue() for u in out_utxoSelect])
        assert utxo_value >= total_outvalue + fee
        out_change = utxo_value - total_outvalue - fee
        if out_change > 0:
            recip.append([self.out_addr160, out_change])
        return (out_utxoSelect, recip, out_utxoList)
        
    def combine_tranches(self, left, right):
        return (left[0] + right[0], left[1] + right[1])

    def make_transaction(self, colored_tgen, uncolored_tgen):
        ctranche = colored_tgen()
        fee = MIN_TX_FEE
        while 1:
            utranche = uncolored_tgen(fee)
            wholetx = self.combine_tranches(ctranche, utranche)
            total_value = sum([u.getValue() for u in wholetx[0]])
            want_fee = calcMinSuggestedFees(wholetx[0], total_value, fee)[1]
            if fee <= want_fee:
                break
            else:
                fee = want_fee
        return wholetx, ctranche, utranche
    
    def process_incoming_payments(self, in_utxoList):
        color_recipients = []

        addr_invalue, addr_utxo, addr_outvalue = self.aggregate_incoming_payments(in_utxoList)

        def in_tgen(fee = 0):
            return self.make_in_tranche(addr_utxo, fee)
        def out_tgen(fee = 0):
            return self.make_out_tranche(addr_outvalue, fee)
        
        if self.in_color == -1:
            colored_tgen, uncolored_tgen = out_tgen, in_tgen
        elif self.out_color == -1:
            colored_tgen, uncolored_tgen = it_tgen, out_tgen
        else:
            raise Exception, "Cannot process a case where both are colored"

        wholetx, ctranche, utranche = self.make_transaction(colored_tgen, uncolored_tgen)

        for u in wholetx[0]:
            print u.pprintOneLine()
        
        for r in wholetx[1]:
            print r
        

        txdp = PyTxDistProposal()
        txdp.createFromTxOutSelection(wholetx[0], wholetx[1])
        txdp = self.wallet.signTxDistProposal(txdp)
        finalTx = txdp.prepareFinalTx()
        engine_broadcast_transaction(finalTx)
            
        
"""
autotrade.register(MyInterpreter.context, MyInterpreter.context.walletMap['2CuYKVHwd'], '1FYXko2KSebdiTVpX53mQF14iK7SjjUnPk', '1Es9rUF3pUoLYnChf3bdH9AXsTRETqKQJq', '1FTvznygZdcxoKRs1c3ToA5fnN5S16KS6v', 0.5, 100)
"""

