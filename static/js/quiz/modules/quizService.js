// js/services/quizService.js
import {CSRF_TOKEN, QUIZ_URL} from './constants.js';

export const submitQuizAnswers = async (answers) => {
    try {
        const response = await fetch(QUIZ_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({answers})
        });

        return await response.json();
    } catch (error) {
        console.error('Error submitting quiz answers:', error);
        throw error;
    }
};