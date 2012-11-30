import colordefs
import os
import json
from armoryengine import *
import urllib2

definition_url_template = "http://srv7.coventry.fennec.name:8080/static/colordefs/%s.colordef"
post_definition_url = "http://srv7.coventry.fennec.name:8080/publish"

main = None

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
    AddColorDefinition(colordef)
    main.populateColorCombo()

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
    main.broadcastTransaction(finalTx)
    
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

