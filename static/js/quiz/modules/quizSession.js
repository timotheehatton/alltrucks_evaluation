// js/models/QuizSession.js
import {loadFromStorage, removeFromStorage, saveToStorage} from './storage.js';
import {CATEGORY_QUESTION_LIMITS} from './constants.js';
import {QuizQuestion} from './QuizQuestion.js';
import {calculateRemainingTime, formatTime} from './timeUtils.js';
import {submitQuizAnswers} from './quizService.js';

export class QuizSession {
    constructor(allQuestions) {
        this.allQuestions = allQuestions.map(q => new QuizQuestion(q));
        this.questions = this.getRandomQuestionsByCategory();
        this.userAnswers = loadFromStorage('userAnswers', {});
        this.currentQuestionIndex = this.determineStartingQuestion();
        this.timerInterval = null;
    }

    getRandomQuestionsByCategory() {
        const categorizedQuestions = {};

        // Group questions by category
        this.allQuestions.forEach(question => {
            const category = question.category;
            if (!categorizedQuestions[category]) {
                categorizedQuestions[category] = [];
            }
            categorizedQuestions[category].push(question);
        });

        const selectedQuestions = [];

        // Select random questions per category based on limits from Django template
        Object.keys(categorizedQuestions).forEach(category => {
            const limit = CATEGORY_QUESTION_LIMITS[category] || 1; // Default to 1 if no limit is specified
            const shuffled = [...categorizedQuestions[category]].sort(() => Math.random() - 0.5);
            selectedQuestions.push(...shuffled.slice(0, limit));
        });

        return selectedQuestions;
    }

    determineStartingQuestion() {
        const savedIndex = parseInt(loadFromStorage('currentQuestionIndex'), 10);
        if (!isNaN(savedIndex)) {
            return savedIndex;
        }

        // Find first unanswered question
        for (let i = 0; i < this.questions.length; i++) {
            if (!this.userAnswers[this.questions[i].id]) {
                return i;
            }
        }

        return 0;
    }

    getCurrentQuestion() {
        return this.questions[this.currentQuestionIndex];
    }

    saveAnswer(choice) {
        const currentQuestion = this.getCurrentQuestion();
        if (!currentQuestion) return false;

        this.userAnswers[currentQuestion.id] = {
            category: currentQuestion.category,
            choice: [choice]
        };

        saveToStorage('userAnswers', this.userAnswers);
        return true;
    }

    moveToNextQuestion() {
        if (this.currentQuestionIndex < this.questions.length - 1) {
            this.currentQuestionIndex++;
            saveToStorage('currentQuestionIndex', this.currentQuestionIndex);
            return true;
        }
        return false;
    }

    isLastQuestion() {
        return this.currentQuestionIndex >= this.questions.length - 1;
    }

    isQuizComplete() {
        return Object.keys(this.userAnswers).length >= this.questions.length;
    }

    async submitQuiz() {
        try {
            const result = await submitQuizAnswers(this.userAnswers);
            if (result.success) {
                this.clearQuizData();
            }
            return result;
        } catch (error) {
            console.error('Error submitting quiz:', error);
            return {success: false, error: 'Failed to submit quiz'};
        }
    }

    clearQuizData() {
        removeFromStorage('userAnswers', 'currentQuestionIndex', 'quizEndTime', 'quizTimer');
    }

    resetTimer() {
        removeFromStorage('quizEndTime', 'quizTimer');
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    startTimer(timerElement, duration = 3600, onTimeout) {
        let timer = duration;

        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }

        this.timerInterval = setInterval(() => {
            timerElement.textContent = formatTime(timer);

            if (--timer < 0) {
                clearInterval(this.timerInterval);
                this.timerInterval = null;
                if (typeof onTimeout === 'function') {
                    onTimeout();
                }
            }

            saveToStorage('quizTimer', timer);
        }, 1000);

        return this.timerInterval;
    }

    initializeTimer(timerElement, onTimeout) {
        let endTime = parseInt(loadFromStorage('quizEndTime'), 10);

        if (!endTime) {
            const duration = 60 * 60 * 1000; // 1 hour in milliseconds
            endTime = Date.now() + duration;
            saveToStorage('quizEndTime', endTime);
        }

        const remainingTime = calculateRemainingTime(endTime);
        if (remainingTime > 0) {
            this.startTimer(timerElement, remainingTime, onTimeout);
            return true;
        }

        return false;
    }
}