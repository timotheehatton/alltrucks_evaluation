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
            imageLoader: document.querySelector('.quiz-image-loader'),
            nextBtn: document.querySelector('.quiz-next'),
            choiceInputs: document.querySelectorAll('input[name="choice"]'),
            answerLabels: Array.from({length: 5}, (_, i) => document.querySelector(`.answer-${i + 1}`)),
            progressBar: document.querySelector('.quiz-progressbar'),
            modalTrigger: document.querySelector('.modal-trigger'),
            modal: document.querySelector('.modal'),
            timeoutMessage: document.querySelector('.timeout-message'),
            successMessage: document.querySelector('.success-message')
        };

        this.currentImageUrl = null;
        this.imageRetryCount = 0;
        this.maxImageRetries = 2;
        this.preloadedImages = new Map();

        this.initEventListeners();
        this.initImageHandlers();
    }

    initImageHandlers() {
        if (this.elements.image) {
            this.elements.image.addEventListener('load', () => this.onImageLoad());
            this.elements.image.addEventListener('error', () => this.onImageError());
        }
    }

    isCurrentImage() {
        // Browser normalizes URLs, so we need to check if current src contains our URL
        return this.currentImageUrl && this.elements.image.src.includes(this.currentImageUrl.split('?')[0]);
    }

    onImageLoad() {
        if (this.isCurrentImage()) {
            this.imageRetryCount = 0;
            this.showImage();
        }
    }

    onImageError() {
        if (!this.isCurrentImage()) return;

        if (this.imageRetryCount < this.maxImageRetries) {
            this.imageRetryCount++;
            console.warn(`Image load failed, retry ${this.imageRetryCount}/${this.maxImageRetries}: ${this.currentImageUrl}`);
            setTimeout(() => {
                if (this.isCurrentImage()) {
                    // Add cache-busting query param for retry
                    const retryUrl = this.currentImageUrl + (this.currentImageUrl.includes('?') ? '&' : '?') + 'retry=' + this.imageRetryCount;
                    this.elements.image.src = retryUrl;
                }
            }, 500 * this.imageRetryCount);
        } else {
            console.error(`Image failed to load after ${this.maxImageRetries} retries: ${this.currentImageUrl}`);
            this.hideImage();
        }
    }

    showImage() {
        if (this.elements.imageLoader) this.elements.imageLoader.style.display = 'none';
        this.elements.image.style.display = 'block';
        this.elements.image.style.opacity = '1';
    }

    hideImage() {
        if (this.elements.imageLoader) this.elements.imageLoader.style.display = 'none';
        this.elements.image.style.display = 'none';
    }

    showImageLoader() {
        this.elements.image.style.display = 'none';
        if (this.elements.imageLoader) this.elements.imageLoader.style.display = 'block';
    }

    preloadImages() {
        const questions = this.quizSession.questions;
        questions.forEach((question, index) => {
            if (question.image && !this.preloadedImages.has(question.image)) {
                const img = new Image();
                img.src = question.image;
                this.preloadedImages.set(question.image, img);
            }
        });
    }

    initEventListeners() {
        this.elements.nextBtn.addEventListener('click', () => this.handleNextButtonClick());

        
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

        // Display or hide image with retry support
        if (question.image) {
            this.currentImageUrl = question.image;
            this.imageRetryCount = 0;
            this.showImageLoader();
            this.elements.image.src = question.image;
        } else {
            this.currentImageUrl = null;
            this.hideImage();
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
