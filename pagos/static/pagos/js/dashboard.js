document.addEventListener("DOMContentLoaded", () => {

    console.log("[dashboard.js] versión JSON script activa ✅");

    const chartEl = document.getElementById('flujoChart');
    console.log("[dashboard.js] canvas flujoChart:", chartEl);

    if (!chartEl) return;

    const dataEl = document.getElementById('flujo-chart-data');
    console.log("[dashboard.js] script flujo-chart-data:", dataEl);

    if (!dataEl) {
        console.warn("[dashboard.js] No se encontró #flujo-chart-data");
        return;
    }

    const raw = (dataEl.textContent || '').trim();
    console.log("[dashboard.js] raw JSON:", raw);

    if (!raw || raw === 'undefined' || raw === 'None') {
        console.warn("[dashboard.js] flujo_chart_json vacío/undefined:", raw);
        return;
    }

    let payload = null;
    try {
        payload = JSON.parse(raw);
    } catch (e) {
        console.error("[dashboard.js] JSON inválido:", e, raw);
        return;
    }

    console.log("[dashboard.js] payload parseado:", payload);

    const labels = payload.labels || [];
    const valores = payload.valores || [];

    if (!labels.length || !valores.length) {
        console.warn("[dashboard.js] payload sin labels/valores:", payload);
        return;
    }

    // Si el canvas no tiene alto visible, Chart.js se ve "en blanco"
    // (tu CSS define .chart-container height: 340px, así que debería ok)
    console.log("[dashboard.js] chart-container height:", chartEl.parentElement?.clientHeight);

    new Chart(chartEl, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Flujo proyectado',
                data: valores,
                fill: true,
                tension: 0.4,
                borderWidth: 3,
                pointRadius: 5,
                pointHoverRadius: 8,
                backgroundColor: 'rgba(79,70,229,0.08)',
                borderColor: '#4f46e5'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const rawVal = String(context.formattedValue || '');
                            const formatted = rawVal.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
                            return '$' + formatted;
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: {
                        callback: function(value) {
                            return '$' + Number(value).toLocaleString('es-CL');
                        }
                    },
                    grid: { color: '#eef2f7' }
                },
                x: {
                    grid: { display: false }
                }
            }
        }
    });

    console.log("[dashboard.js] Chart creado ✅");

});