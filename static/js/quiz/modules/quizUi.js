export class QuizUi {
    constructor(quizSession) {
        this.quizSession = quizSession;
        this.elements = {
            timer: document.querySelector('.quiz-timer'),
            progress: document.querySelector('.quiz-progress-number'),
            category: document.querySelector('.quiz-category'),
            category_position: document.querySelector('.quiz-category-position'),
            question: document.querySelector('.quiz-question'),
            image: document.querySelector('.quiz-image'),
            nextBtn: document.querySelector('.quiz-next'),
            choiceInputs: document.querySelectorAll('input[name="choice"]'),
            answerLabels: Array.from({length: 5}, (_, i) => document.querySelector(`.answer-${i + 1}`)),
            progressBar: document.querySelector('.quiz-progressbar'),
            modalTrigger: document.querySelector('.modal-trigger'),
            modal: document.querySelector('.modal'),
            timeoutMessage: document.querySelector('.timeout-message'),
            successMessage: document.querySelector('.success-message')
        };

        this.initEventListeners();
    }

    initEventListeners() {
        // Next button click
        this.elements.nextBtn.addEventListener('click', () => this.handleNextButtonClick());

        // Choice inputs change
        this.elements.choiceInputs.forEach(input => {
            input.addEventListener('change', () => this.enableNextButton());
        });

        // Modal trigger
        if (this.elements.modalTrigger) {
            this.elements.modalTrigger.addEventListener('click', () => {
                this.quizSession.initializeTimer(this.elements.timer, () => this.handleTimeout());
            });
        }
    }

    handleNextButtonClick() {
        const selectedChoices = Array.from(this.elements.choiceInputs)
            .filter(input => input.checked)
            .map(input => input.value);

        if (selectedChoices.length) {
            this.quizSession.saveAnswer(selectedChoices[0]);

            if (this.quizSession.isLastQuestion()) {
                this.handleQuizCompletion();
            } else {
                this.quizSession.moveToNextQuestion();
                this.displayCurrentQuestion();
            }
        }
    }

    async handleQuizCompletion() {
        const result = await this.quizSession.submitQuiz();
        if (result.success) {
            this.showSuccessMessage();
            this.quizSession.resetTimer();
        }
    }

    handleTimeout() {
        this.showTimeoutMessage();
        this.quizSession.submitQuiz().then(() => {
            this.quizSession.resetTimer();
        });
    }

    showTimeoutMessage() {
        const modalContent = document.querySelector('.modal-content');
        if (modalContent) modalContent.style.display = 'none';
        if (this.elements.timeoutMessage) this.elements.timeoutMessage.style.display = 'block';
    }

    showSuccessMessage() {
        const modalContent = document.querySelector('.modal-content');
        if (modalContent) modalContent.style.display = 'none';
        if (this.elements.successMessage) this.elements.successMessage.style.display = 'block';
    }

    displayCurrentQuestion() {
        const question = this.quizSession.getCurrentQuestion();
        if (!question) return;
        this.elements.progress.innerText = `${this.quizSession.currentQuestionIndex + 1}/${this.quizSession.questions.length}`;
        this.elements.category.innerText = question.category_displayed;

        // Calculate category progress
        const currentCategory = question.category;
        const questionsInCategory = this.quizSession.questions.filter(q => q.category === currentCategory);
        const totalQuestionsInCategory = questionsInCategory.length;

        // Find the position of the current question within its category
        const currentQuestionInCategory = questionsInCategory.findIndex(q => q.id === question.id) + 1;

        // Display category progress
        this.elements.category_position.innerText = `${currentQuestionInCategory}/${totalQuestionsInCategory}`;
        this.elements.question.innerText = question.question;

        // Display or hide image
        if (question.image) {
            this.elements.image.src = question.image;
            this.elements.image.style.display = 'block';
        } else {
            this.elements.image.style.display = 'none';
        }

        // Set up answer choices
        this.elements.answerLabels.forEach((label, i) => {
            if (i < question.choices.length) {
                label.style.display = 'block';
                label.querySelector('span').innerText = question.choices[i];
            } else {
                label.style.display = 'none';
            }
        });

        // Reset choice inputs
        this.elements.choiceInputs.forEach(input => (input.checked = false));

        // Update next button state
        this.disableNextButton();

        // Update progress bar
        this.updateProgressBar();
    }

    enableNextButton() {
        const isAnyChecked = Array.from(this.elements.choiceInputs).some(input => input.checked);
        this.elements.nextBtn.classList.toggle('disabled', !isAnyChecked);
        this.elements.nextBtn.classList.toggle('blue', isAnyChecked);
    }

    disableNextButton() {
        this.elements.nextBtn.classList.add('disabled');
        this.elements.nextBtn.classList.remove('blue');
    }

    updateProgressBar() {
        const progress = (this.quizSession.currentQuestionIndex / this.quizSession.questions.length) * 100;
        this.elements.progressBar.style.width = `${progress}%`;
    }

    initializeModal() {
        if (window.M && this.elements.modal) {
            const modalInstance = M.Modal.init(this.elements.modal, {dismissible: false});
            return modalInstance;
        }
        return null;
    }
}
