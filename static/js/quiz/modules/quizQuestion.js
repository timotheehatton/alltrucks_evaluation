export class QuizQuestion {
    constructor(questionData) {
        this.id = questionData.id;
        this.category = questionData.category;
        this.category_displayed = questionData.category_displayed;
        this.question = questionData.question;
        this.image = questionData.image || null;
        this.choices = this.extractChoices(questionData);
    }

    extractChoices(data) {
        const choices = [];
        for (let i = 1; i <= 5; i++) {
            const choice = data[`choice_${i}`];
            if (choice) {
                choices.push(choice);
            }
        }
        return choices;
    }
}