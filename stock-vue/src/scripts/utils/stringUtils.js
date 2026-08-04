import CryptoJS from "crypto-js";

const RANDOM_LEN =3;

export const createStatusKey = () => {
    const preKey = generateRandomString(RANDOM_LEN);
    const postKey = generateRandomString(RANDOM_LEN);
    return encryptString(preKey.concat(aibeesGlobal.SERVICE_KEY).concat(postKey));
}

export const extractStatusKey = (str) => {
    const decrypted = decryptString(str.replace(/ /g, '+'));
    return decrypted.slice(RANDOM_LEN, (-1)*RANDOM_LEN);
}

const encryptString = (str) => {
    return CryptoJS.AES.encrypt(str, aibeesGlobal.ENCRYPT_KEY).toString();
}

const decryptString = (str) => {
    const decyprted = CryptoJS.AES.decrypt(str, aibeesGlobal.ENCRYPT_KEY).toString(CryptoJS.enc.Utf8);
    return decyprted;
}

const generateRandomString = (num) => {
    const characters ='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    const charactersLength = characters.length;
    for (let i = 0; i < num; i++) {
        result += characters.charAt(Math.floor(Math.random() * charactersLength));
    }

    return result;
}

export const isEmpty = (str) => {
    return str === undefined || str === null || str == '';
}