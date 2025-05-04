let update = false;
const htmlLegendPlugin = {
    id: 'htmlLegend', afterUpdate(chart, args, options) {
        const ul = document.getElementById(options.containerID);
        while (ul.firstChild) {
            ul.firstChild.remove();
        }
        const items = chart.options.plugins.legend.labels.generateLabels(chart);
        items.forEach((item, index) => {
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.alignItems = 'center';
            const svgIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svgIcon.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
            svgIcon.setAttribute('height', '24px');
            svgIcon.setAttribute('viewBox', '0 -960 960 960');
            svgIcon.setAttribute('width', '24px');
            svgIcon.setAttribute('fill', item.strokeStyle);
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', 'M480-480q-66 0-113-47t-47-113q0-66 47-113t113-47q66 0 113 47t47 113q0 66-47 113t-113 47ZM160-160v-112q0-34 17.5-62.5T224-378q62-31 126-46.5T480-440q66 0 130 15.5T736-378q29 15 46.5 43.5T800-272v112H160Z');
            svgIcon.appendChild(path);
            const anchor = document.createElement('a');
            anchor.style.color = item.fontColor;
            anchor.style.textDecoration = item.hidden ? 'line-through' : 'none';
            const isAdmin = document.body.dataset.isAdmin === 'true';
            anchor.href = `${isAdmin ? '/admin/user/' : '/manager/technician/'}${chart.data.datasets[index].technicianId}/`;
            anchor.textContent = item.text;

            li.appendChild(svgIcon);
            li.appendChild(anchor);
            ul.appendChild(li);
            li.addEventListener('mouseenter', () => {
                if (update == false) {
                    update = true;
                    chart.getDatasetMeta(index).hidden = false;
                    chart.data.datasets.forEach((dataset, i) => {
                        if (i !== index) {
                            chart.getDatasetMeta(i).hidden = true;
                        }
                    });
                    chart.update();
                }
            });
            li.addEventListener('mouseleave', () => {
                update = false;
                chart.data.datasets.forEach((_, i) => {
                    chart.getDatasetMeta(i).hidden = false;
                });
                chart.update();
            });
        });
    }
};
Chart.register(htmlLegendPlugin);

const ctx = document.getElementById('radarChart').getContext('2d');
const data = {
    labels: Object.keys(GLOBAL_SCORE), datasets: TECHNICIAN_SCORES.map(technician => ({
        label: technician.name,
        technicianId: technician.id,
        data: Object.values(technician.values),
        fill: false,
        pointRadius: 0,
        borderWidth: 4
    }))
};

const radarChart = new Chart(ctx, {
    type: 'radar', data: data, options: {
        responsive: true, maintainAspectRatio: false, plugins: {
            htmlLegend: {
                containerID: 'legend-container'
            }, legend: {
                display: false
            },
        }, scales: {
            r: {
                min: 0, max: 100, ticks: {
                    display: false
                }, angleLines: {
                    display: true
                }, grid: {
                    drawBorder: true, drawOnChartArea: false
                }, pointLabels: {
                    font: {
                        size: 13, weight: 'bold',
                    },
                }, beginAtZero: true
            }
        }
    }
});