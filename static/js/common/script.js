var sidenav = document.querySelectorAll('.sidenav');
var sidenav = M.Sidenav.init(sidenav);
var select = document.querySelectorAll('select');
var select = M.FormSelect.init(select);
const loader = document.getElementById('global-loader');
const rows = document.querySelectorAll('.clickable-row');


rows.forEach(row => {
    row.addEventListener('click', function () {
        window.location = this.dataset.href;
    });
});

function showLoader() {
    setTimeout(() => {
        loader.style.display = 'flex';
    }, 60);
}

document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', showLoader);
});

document.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', function (event) {
        const href = link.getAttribute('href');
        if (href && !href.startsWith('#')) {
            showLoader();
        }
    });
});

document.querySelectorAll('.clickable-row').forEach(row => {
    row.addEventListener('click', function () {
        const href = row.getAttribute('data-href');
        if (href) {
            showLoader();
            window.location.href = href;
        }
    });
});