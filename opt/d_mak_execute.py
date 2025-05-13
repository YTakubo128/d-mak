import json
import time
import hashlib
import hmac
import base64
import uuid
import requests

def executeOne():
    #操作したいデバイスのIDをここに入力
    device_id = "xxxxxxxxxxx"

    # Declare empty header dictionary
    apiHeader = {}
    # open token
    token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' # copy and paste from the SwitchBot app V6.14 or later
    # secret key
    secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxx' # copy and paste from the SwitchBot app V6.14 or later
    nonce = uuid.uuid4()
    t = int(round(time.time() * 1000))
    string_to_sign = '{}{}{}'.format(token, t, nonce)

    string_to_sign = bytes(string_to_sign, 'utf-8')
    secret = bytes(secret, 'utf-8')

    sign = base64.b64encode(hmac.new(secret, msg=string_to_sign, digestmod=hashlib.sha256).digest())
    #print ('Authorization: {}'.format(token))
    #print ('t: {}'.format(t))
    #print ('sign: {}'.format(str(sign, 'utf-8')))
    #print ('nonce: {}'.format(nonce))

    #Build api header JSON
    apiHeader['Authorization']=token
    apiHeader['Content-Type']='application/json'
    apiHeader['charset']='utf8'
    apiHeader['t']=str(t)
    apiHeader['sign']=str(sign, 'utf-8')
    apiHeader['nonce']=str(nonce)

    response = requests.get(
        f"https://api.switch-bot.com/v1.1/devices/{device_id}/status",
        headers=apiHeader,
    )
    parsed_response = json.loads(response.text)
    power_state = parsed_response['body']['power']
    #print("Power state:", power_state)

    if (power_state == "on"):
        param = {
            "command": "turnOff",
            "parameter": "default",
            "commandType": "command"
        }
    elif (power_state == "off"):
        param = {
            "command": "turnOn",
            "parameter": "default",
            "commandType": "command"
        }


    if 'param' in locals() or 'param' in globals():
        param_json = json.dumps(param)
        status = requests.post(f"https://api.switch-bot.com/v1.1/devices/{device_id}/commands", param_json, headers=apiHeader)
        #print(status.text)

if __name__ == '__main__':
    executeOne()