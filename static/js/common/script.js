var sidenav = document.querySelectorAll('.sidenav');
var sidenav = M.Sidenav.init(sidenav);
var select = document.querySelectorAll('select');
var select = M.FormSelect.init(select);

const rows = document.querySelectorAll('.clickable-row');
rows.forEach(row => {
    row.addEventListener('click', function () {
        window.location = this.dataset.href;
    });
});