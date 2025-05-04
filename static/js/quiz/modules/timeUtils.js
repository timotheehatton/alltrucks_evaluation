export const formatTime = (totalSeconds) => {
    const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
    const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
    const seconds = String(Math.floor(totalSeconds % 60)).padStart(2, '0');

    return `${hours}:${minutes}:${seconds}`;
};

export const calculateRemainingTime = (endTime) => {
    const now = Date.now();
    return Math.max((endTime - now) / 1000, 0);
};