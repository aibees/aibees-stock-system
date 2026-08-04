from app.common.utils.aesUtils import aesUtils

def test():
    testText = '3EEwAjHTHbyxTq4r0DP4MfGYF2XoAtmdRCWJSvfX'
    testText2 = 'QtIf0MFGODp36oxxBZoF9zTn3MqEq06bvzjkycrk'
    encryptText = aesUtils.encrypt(testText)
    print("encrypt : " + encryptText)
    encryptText2 = aesUtils.encrypt(testText2)
    print("encrypt2 : " + encryptText2)
    
    decryptText = aesUtils.decrypt(encryptText)
    print("decrypt : " + decryptText)