var elems = document.querySelectorAll('.sidenav');
var instances = M.Sidenav.init(elems);

var elems = document.querySelectorAll('select');
var instances = M.FormSelect.init(elems);

const rows = document.querySelectorAll('.clickable-row');
rows.forEach(row => {
    row.addEventListener('click', function () {
        window.location = this.dataset.href;
    });
});