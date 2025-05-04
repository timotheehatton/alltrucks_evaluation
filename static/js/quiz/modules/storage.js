export const loadFromStorage = (key, defaultValue = null) => {
    try {
        const value = localStorage.getItem(key);
        return value ? JSON.parse(value) : defaultValue;
    } catch (error) {
        console.error(`Error loading ${key} from storage:`, error);
        return defaultValue;
    }
};

export const saveToStorage = (key, value) => {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch (error) {
        console.error(`Error saving ${key} to storage:`, error);
        return false;
    }
};

export const removeFromStorage = (...keys) => {
    keys.forEach(key => {
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.error(`Error removing ${key} from storage:`, error);
        }
    });
};