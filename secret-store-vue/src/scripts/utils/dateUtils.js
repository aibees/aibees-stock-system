
export const nowKST = () => {
    const curr = new Date();
    // 2. UTC 시간 계산
    const utc = curr.getTime() + (curr.getTimezoneOffset() * 60 * 1000);

    // 3. UTC to KST (UTC + 9시간)
    return new Date(utc + (9 * 60 * 60 * 1000));
}

export const getDayStr = (dayCode) => {
    const dayMap = {
        0: '일요일',
        1: '월요일',
        2: '화요일',
        3: '수요일',
        4: '목요일',
        5: '금요일',
        6: '토요일'
    }

    return dayMap[dayCode]
}