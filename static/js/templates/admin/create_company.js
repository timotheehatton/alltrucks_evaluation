let technicianCount = 1;

function addTechnician() {
    technicianCount++;
    const container = document.getElementById('technicians-container');
    const template = document.querySelector('.technician-group').cloneNode(true);

    template.querySelectorAll('input').forEach((input) => {
        const oldId = input.id;
        const oldName = input.name;
        const newId = oldId.replace(/_\d+$/, `_${technicianCount}`);
        const newName = oldName.replace(/_\d+$/, `_${technicianCount}`);
        input.id = newId;
        input.name = newName;
        input.value = '';
    });

    template.querySelectorAll('label').forEach((label) => {
        const oldFor = label.htmlFor;
        label.htmlFor = oldFor.replace(/_\d+$/, `_${technicianCount}`);
    });

    container.appendChild(template);
}

function removeTechnician(element) {
    element.parentElement.remove();
}