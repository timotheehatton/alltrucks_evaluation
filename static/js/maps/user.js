let radarChart;

function initializeChart() {
    const ctx = document.getElementById('radarChart').getContext('2d');

    const labels = SCORES_BY_CATEGORY.map(score => score.question_type);
    const scores = SCORES_BY_CATEGORY.map(score => score.success_percentage);

    const data = {
        labels: labels,
        datasets: [
            {
                data: scores,
                fill: false,
                pointRadius: 0,
                borderWidth: 4
            }
        ]
    };

    radarChart = new Chart(ctx, {
        type: 'radar',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    pointLabels: {
                        display: false
                    },
                    ticks: {
                        display: false
                    },
                    angleLines: {
                        display: true
                    },
                    grid: {
                        drawBorder: true,
                        drawOnChartArea: false,
                    },
                    pointLabels: {
                        font: {
                            size: 14,
                            weight: 'bold'
                        },
                        padding: 10,
                        callback: function (label) {
                            const words = label.split(' ');
                            const maxWidth = 27;
                            let lines = [];
                            let currentLine = words[0];

                            for (let i = 1; i < words.length; i++) {
                                if (currentLine.length + words[i].length + 1 <= maxWidth) {
                                    currentLine += ' ' + words[i];
                                } else {
                                    lines.push(currentLine);
                                    currentLine = words[i];
                                }
                            }
                            lines.push(currentLine);
                            return lines;
                        }
                    },
                    beginAtZero: true
                }
            },
            plugins: {
                tooltip: {
                    enabled: false
                },
                legend: {
                    display: false
                }
            },
            animation: {
                onComplete: function () {
                    const chartInstance = this;
                    const ctx = chartInstance.ctx;
                    const chartArea = chartInstance.chartArea;
                    ctx.font = Chart.helpers.fontString(11, "bold", Chart.defaults.font.family);
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';

                    chartInstance.data.datasets.forEach((dataset, i) => {
                        const meta = chartInstance.getDatasetMeta(i);
                        ctx.fillStyle = dataset.borderColor || 'blue';
                        meta.data.forEach((point, index) => {
                            const data = `${dataset.data[index]}%`;
                            const angle = point.angle;
                            const offset = 15;
                            const posX = point.x + Math.cos(angle) * offset;
                            const posY = point.y + Math.sin(angle) * offset;
                            ctx.fillText(data, posX, posY);
                        });
                    });
                }
            }
        }
    });
}

initializeChart();

document.querySelector('.download-pdf').addEventListener('click', function () {
    const image = radarChart.toBase64Image();

    fetch(DOWNLOAD_PDF_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({chart_image_base64: image})
    })
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'diploma.pdf';
            document.body.appendChild(a);
            a.click();
            a.remove();
        })
        .catch(error => console.error('Error:', error));
});