(() => {
  const dataScript = document.getElementById('dashboard-data');
  if (!dataScript) {
    return;
  }

  let payload;
  try {
    payload = JSON.parse(dataScript.textContent || '{}');
  } catch (error) {
    console.error('无法解析仪表盘数据：', error);
    return;
  }

  const {
    monthlyLabels = [],
    monthlyWithdrawals = [],
    monthlyDeposits = [],
    monthlyTransfers = [],
    spendingCategories = [],
    incomeCategories = [],
    transferAccounts = []
  } = payload;

  if (typeof Chart === 'undefined') {
    console.error('Chart.js 未加载，无法渲染图表');
    return;
  }

  Chart.defaults.font.family = "'Inter', 'Segoe UI', sans-serif";
  Chart.defaults.color = '#dee2e6';
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15, 23, 42, 0.85)';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(148, 163, 184, 0.25)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;

  const palette = {
    withdrawal: '#ff6b6b',
    deposit: '#4dabf7',
    transfer: '#f7b84b',
    neutral: '#ced4da'
  };

  const datasetHasValue = data => Array.isArray(data) && data.some(value => Number(value) !== 0);
  const tupleHasValue = data => Array.isArray(data) && data.some(item => Number(item?.[1]) !== 0);
  const formatCurrency = value => `¥${Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;

  const showEmptyState = (canvas, message) => {
    const container = canvas.parentElement;
    if (!container) {
      return;
    }
    const placeholder = container.querySelector('[data-role="empty-state"]');
    if (placeholder) {
      placeholder.textContent = message;
      placeholder.hidden = false;
    }
    canvas.hidden = true;
  };

  const hideEmptyState = canvas => {
    const container = canvas.parentElement;
    if (!container) {
      return;
    }
    const placeholder = container.querySelector('[data-role="empty-state"]');
    if (placeholder) {
      placeholder.hidden = true;
    }
    canvas.hidden = false;
  };

  const builderMap = new Map();
  const chartInstances = new Map();

  const instantiateChart = canvas => {
    if (chartInstances.has(canvas)) {
      return;
    }
    const factory = builderMap.get(canvas);
    if (!factory) {
      return;
    }
    hideEmptyState(canvas);
    const config = factory(canvas);
    const chart = new Chart(canvas.getContext('2d'), config);
    chartInstances.set(canvas, chart);
  };

  const observer = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const canvas = entry.target;
            obs.unobserve(canvas);
            instantiateChart(canvas);
          }
        });
      }, { rootMargin: '160px' })
    : null;

  const registerChart = (canvas, factory) => {
    if (!canvas) {
      return;
    }
    builderMap.set(canvas, factory);
    if (observer) {
      observer.observe(canvas);
    } else {
      instantiateChart(canvas);
    }
  };

  const monthlyCanvas = document.getElementById('monthlyTrends');
  const hasMonthlyData = [monthlyWithdrawals, monthlyDeposits, monthlyTransfers].some(datasetHasValue);
  if (monthlyCanvas) {
    if (!hasMonthlyData) {
      showEmptyState(monthlyCanvas, '暂无月度趋势数据');
    } else {
      registerChart(monthlyCanvas, () => ({
        type: 'line',
        data: {
          labels: monthlyLabels,
          datasets: [
            {
              label: '支出',
              data: monthlyWithdrawals,
              borderColor: palette.withdrawal,
              backgroundColor: 'rgba(255, 107, 107, 0.12)',
              tension: 0.35,
              fill: true,
              pointRadius: 3,
              pointHoverRadius: 5,
              borderWidth: 2
            },
            {
              label: '收入',
              data: monthlyDeposits,
              borderColor: palette.deposit,
              backgroundColor: 'rgba(77, 171, 247, 0.12)',
              tension: 0.35,
              fill: true,
              pointRadius: 3,
              pointHoverRadius: 5,
              borderWidth: 2
            },
            {
              label: '转账',
              data: monthlyTransfers,
              borderColor: palette.transfer,
              backgroundColor: 'rgba(247, 184, 75, 0.14)',
              tension: 0.35,
              fill: true,
              pointRadius: 3,
              pointHoverRadius: 5,
              borderWidth: 2
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: {
            duration: 600,
            easing: 'easeOutQuart'
          },
          responsiveAnimationDuration: 240,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            decimation: {
              enabled: true,
              algorithm: 'min-max'
            },
            legend: {
              labels: {
                color: '#f1f3f5'
              }
            },
            tooltip: {
              callbacks: {
                label: context => {
                  const value = context.parsed.y || 0;
                  return `${context.dataset.label}: ${formatCurrency(value)}`;
                }
              }
            }
          },
          scales: {
            x: {
              ticks: { color: '#dee2e6' },
              grid: { color: 'rgba(255, 255, 255, 0.05)' }
            },
            y: {
              ticks: {
                color: '#dee2e6',
                callback: value => formatCurrency(value).replace('¥', '¥ ')
              },
              grid: { color: 'rgba(255, 255, 255, 0.08)' }
            }
          }
        }
      }));
    }
  }

  const horizontalChart = (canvas, dataset, color, emptyMessage) => {
    if (!canvas) {
      return;
    }
    if (!tupleHasValue(dataset)) {
      showEmptyState(canvas, emptyMessage);
      return;
    }

    registerChart(canvas, () => {
      const labels = dataset.map(item => item?.[0] ?? '未命名');
      const values = dataset.map(item => Number(item?.[1]) || 0);
      const maxValue = Math.max(...values, 0);
      const padding = maxValue > 0 ? maxValue * 0.15 : 1;

      return {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              data: values,
              backgroundColor: color,
              borderRadius: 10,
              hoverBackgroundColor: color,
              maxBarThickness: 28
            }
          ]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          animation: {
            duration: 480,
            easing: 'easeOutQuart'
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: context => formatCurrency(context.parsed.x)
              }
            }
          },
          scales: {
            x: {
              ticks: { color: '#dee2e6' },
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              suggestedMax: maxValue + padding
            },
            y: {
              ticks: { color: '#dee2e6' },
              grid: { display: false }
            }
          }
        }
      };
    });
  };

  horizontalChart(
    document.getElementById('spendingCategories'),
    spendingCategories,
    palette.withdrawal,
    '暂无支出类别数据'
  );
  horizontalChart(
    document.getElementById('incomeCategories'),
    incomeCategories,
    palette.deposit,
    '暂无收入类别数据'
  );
  horizontalChart(
    document.getElementById('transferAccounts'),
    transferAccounts,
    palette.transfer,
    '暂无转账账户数据'
  );
})();
