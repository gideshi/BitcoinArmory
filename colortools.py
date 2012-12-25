import colordefs
import os
import json
from armoryengine import *
import urllib2

definition_url_template = "http://srv7.coventry.fennec.name:8080/static/colordefs/%s.colordef"
post_definition_url = "http://srv7.coventry.fennec.name:8080/publish"

def store_color_def(colordef):
    colorid = colordef['colorid']
    path = os.path.join(ARMORY_HOME_DIR, "colordefs", "%s.colordef" % colorid)
    with open(path, "w") as f:
        json.dump([colordef], f, indent = True)

def delete_color_def(colorid):
    path = os.path.join(ARMORY_HOME_DIR, "colordefs", "%s.colordef" % colorid)
    if os.path.exists(path):
        os.remove(path)
    

def install_color_def(colordef):
    store_color_def(colordef)
    AddColorDefinition(colordef, notify=True)

def issue_colored_coins(wallet, toaddr, amount_in_units, partial_definition):
    utxoList = wallet.getTxOutListX(-1, 'Spendable')
    unit = partial_definition.get('unit', 1)
    satoshis = int(amount_in_units * unit)
    coinz = PySelectCoins(utxoList, satoshis, 0)
    if not coinz:
        raise Exception("Not enough coins, need %s satoshi" % satoshis)
    fee = calcMinSuggestedFees(coinz, satoshis, 0)[1]
    coinz = PySelectCoins(utxoList, satoshis, fee)
    if not coinz:
        raise Exception("Not enough coins, need %s satoshi + %s fee" % \
                            (satoshis, fee))
    recipientPairs = [[addrStr_to_hash160(toaddr), satoshis]]
    totalCoinz = sum([u.getValue() for u in coinz])
    if totalCoinz > satoshis + fee:
        change = totalCoinz - satoshis - fee
        changeAddress = coinz[0].getRecipientAddr()
        if wallet.hasAddr(changeAddress):
            recipientPairs.append([changeAddress, change])
        else:
            raise Exception("Don't know what to do with change")
    txdp = PyTxDistProposal()
    txdp.createFromTxOutSelection(coinz, recipientPairs)
    txdp = wallet.signTxDistProposal(txdp)
    finalTx = txdp.prepareFinalTx()
    
    txhash = finalTx.getHash()
    txhash_s = binary_to_hex(txhash, endIn=BIGENDIAN, endOut=LITTLEENDIAN)
    colordef = partial_definition.copy()
    colordef['style'] = 'genesis'
    colordef['issues'] = [{"txhash": txhash_s,
                           "outindex": 0}]
    colordefs.FinalizeColorDefinition(colordef)
    install_color_def(colordef)
    engine_broadcast_transaction(finalTx)
    return colordef['colorid']

def is_url_like(string):
    for prefix in ['http:/', 'https:/', 'ftp:/', 'file:/']:
        if string.startswith(prefix):
            return True
    return False

def fetch_color_definition(colorid):
    if is_url_like(colorid):
        url = colorid
    else:
        url = definition_url_template % colorid

    s = None
    try:
        s = urllib2.urlopen(url)
        content = s.read()
    finally:
        if s:
            s.close()

    colordef = json.loads(content)[0]
    if colordefs.ValidateColorDefinition(colordef) and colordef['colorid'] == colorid:
        return colordef
    else:
        raise Exception("verification failed")

def download_color_definition(colorid):
    install_color_def(fetch_color_definition(colorid))

def find_color_definition(colorid):
    for [colorname, colordef, cd] in color_definitions:
        if colordef['colorid'] == colorid:
            return colordef
    return None

def find_color_index(colorid):
    i = 0
    for [colorname, colordef, cd] in color_definitions:
        if colordef['colorid'] == colorid:
            return i
        i += 1
    return None
    

def upload_color_definition(colorid):
    colordef = find_color_definition(colorid)
    colordef_s = json.dumps([colordef])
    u = urllib2.urlopen(post_definition_url, colordef_s)
    response = u.read()
    if response == "OK":
        return True
    else:
        raise Exception("server did not accept our definition: %s" % response)

def get_output_color_index(txhash, idx):
    return TheBDM.getColorMan().getTxOColor(txhash, idx)

COLOR_UNKNOWN = -2
COLOR_UNCOLORED = -1

def compute_colors(inputs, outputs):
    cur_amount = 0
    cur_color = COLOR_UNKNOWN
    ii = 0
    for o in outputs:
        want_amount = o[0]
        if want_amount > 0:
            while cur_amount < want_amount and ii < len(inputs):
                if cur_amount == 0:
                    cur_color = inputs[ii][1]
                elif cur_color != inputs[ii][1]:
                    cur_color = COLOR_UNCOLORED
                cur_amount += inputs[ii][0]
                ii += 1
            if cur_amount < want_amount:
                return False # transaction is invalid
        else:
            if cur_amount == 0 and ii < len(inputs) and inputs[ii][0] == 0:
                cur_color = inputs[ii][1]
                ii += 1
            else:
                cur_color = COLOR_UNCOLORED
        o[1] = cur_color
        cur_amount -= want_amount
    return True


def compute_pytx_colors(pytx):
    inputs = []
    for inp in pytx.inputs:
        txhash = inp.outpoint.txHash
        outindex = inp.outpoint.txOutIndex
        color = get_output_color_index(txhash, outindex)
        prevtx = TheBDM.getTxByHash(txhash)
        if not prevtx:
            raise Exception("Could not find referenced tx")
        value = prevtx.getTxOut(outindex).getValue()
        inputs.append([value, color])
    print "Inputs", inputs
    outputs = []
    for outpt in pytx.outputs:
        outputs.append([outpt.value, COLOR_UNKNOWN])
    if compute_colors(inputs, outputs):
        outcolors = []
        for o in outputs:
            outcolors.append(o[1])
        return outcolors
    else:
        return None
    
