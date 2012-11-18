from armoryengine import *

"""
autotrade.register(MyInterpreter.context, MyInterpreter.context.walletMap['2CuYKVHwd'], '1FYXko2KSebdiTVpX53mQF14iK7SjjUnPk', '1Es9rUF3pUoLYnChf3bdH9AXsTRETqKQJq', '1FTvznygZdcxoKRs1c3ToA5fnN5S16KS6v', 0.5, 100)
"""

def findMatchingAddr(utxo):
    txhash = utxo.getTxHash()
    tx = TheBDM.getTxByHash(txhash)
    txin = tx.getTxIn(0)
    return TheBDM.getSenderAddr20(txin)

def register(main, wallet, in_addr, accum_addr, out_addr, rate, limit):
    in_addr160 = addrStr_to_hash160(in_addr)
    out_addr160 = addrStr_to_hash160(out_addr)
    accum_addr160 = addrStr_to_hash160(accum_addr)
    color = wallet.color
    if not wallet.hasAddr(in_addr160):
        raise Exception("No in_addr in wallet")
    if not wallet.hasAddr(out_addr160):
        raise Exception("No out_addr in wallet")

    def check_and_trade():
        in_utxoList = wallet.getAddrTxOutListX(-1, in_addr160, 'Spendable')
        if len(in_utxoList) > 0:
            color_recipients = []
            totalValue = 0
            totalCValue = 0
            for utxo in in_utxoList:
                value = utxo.getValue()
                cvalue = int(value * rate)
                addr = findMatchingAddr(utxo)
                if addr:
                    totalValue += value
                    totalCValue += cvalue
                    color_recipients.append([addr, cvalue])

            print ("autotrade: got %s inputs, %s BTC, going to send %s colored coins" % \
                       (len(in_utxoList), totalValue, totalCValue))

            my_utxoList = wallet.getAddrTxOutListX(color, out_addr160, 'Spendable')
            my_utxoSelect = PySelectCoins(my_utxoList, totalCValue, 0)
            if not my_utxoSelect:
                print "Not enough colored coins, aborting"
                return

            all_utxos = my_utxoSelect[:]
            for utxo in in_utxoList:
                all_utxos.append(utxo) 

            fee = calcMinSuggestedFees(all_utxos, totalValue + totalCValue, 0)[1]
            print ("Fee required: %s" % (fee,))
            if fee > totalValue:
                print "Uncolored coins received less than fee required, aborting"
                return
            total_colored = sum([u.getValue() for u in my_utxoSelect])
            colored_change = total_colored - totalCValue
            if colored_change > 0:
                color_recipients.append([out_addr160, colored_change])
            print ("colored coin change: %s" % (colored_change,))
            recipValuePairs = color_recipients + [[accum_addr160, (totalValue - fee)]]

            txdp = PyTxDistProposal()
            txdp.createFromTxOutSelection(all_utxos, recipValuePairs)
            txdp = wallet.signTxDistProposal(txdp)
            finalTx = txdp.prepareFinalTx()
            main.broadcastTransaction(finalTx)
                
    check_and_trade()
    #main.extraHeartbeatFunctions.append(check_and_trade)
    print "registered auto-trade"

