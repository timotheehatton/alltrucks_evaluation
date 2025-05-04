// js/constants.js
// Access globals from window.QUIZ_CONFIG that were set in the Django template

// Export constants from Django template
export const ALL_QUESTIONS = window.QUIZ_CONFIG.ALL_QUESTIONS;
export const QUIZ_URL = window.QUIZ_CONFIG.QUIZ_URL;
export const CSRF_TOKEN = window.QUIZ_CONFIG.CSRF_TOKEN;
export const CATEGORY_QUESTION_LIMITS = window.QUIZ_CONFIG.CATEGORY_QUESTION_LIMITS;