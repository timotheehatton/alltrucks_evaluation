// js/main.js
import {ALL_QUESTIONS} from './modules/constants.js';
import {QuizSession} from './modules/quizSession.js';
import {QuizUi} from './modules/quizUi.js';
import {calculateRemainingTime} from './modules/timeUtils.js';
import {loadFromStorage} from './modules/storage.js';

export function initializeQuiz() {
    // Initialize the quiz
    const quizSession = new QuizSession(ALL_QUESTIONS);
    const quizUI = new QuizUi(quizSession);

    // Display the first question
    quizUI.displayCurrentQuestion();

    // Preload all question images in the background
    quizUI.preloadImages();

    // Initialize modal if using Materialize
    const modalInstance = quizUI.initializeModal();

    // Check if there's an active timer
    const endTime = parseInt(loadFromStorage('quizEndTime'), 10);
    if (endTime) {
        const remainingTime = calculateRemainingTime(endTime);

        // Open the modal if it exists
        if (modalInstance) {
            modalInstance.open();
        }

        if (remainingTime > 0) {
            // Start the timer with remaining time
            quizSession.startTimer(quizUI.elements.timer, () => quizUI.handleTimeout());
        } else {
            // Handle timeout
            quizUI.handleTimeout();
        }
    } else if (quizSession.hasActiveQuiz()) {
        // Orphaned quiz data (timer removed but quiz data remains) — clear it
        quizSession.clearQuizData();
    }
}

initializeQuiz()