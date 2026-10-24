// static/labels/app.js - УПРОЩЕННАЯ ВЕРСИЯ

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Toggle manual time field (только для форм)
    const useManualTime = document.getElementById('{{ form.use_manual_time.id_for_label }}');
    const manualTimeField = document.getElementById('manual-time-field');
    
    if (useManualTime && manualTimeField) {
        function toggleManualTimeField() {
            manualTimeField.style.display = useManualTime.checked ? 'block' : 'none';
        }
        
        useManualTime.addEventListener('change', toggleManualTimeField);
        toggleManualTimeField();
    }

    // Простое закрытие мобильного меню
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        document.querySelectorAll('.nav-link:not(.dropdown-toggle)').forEach(link => {
            link.addEventListener('click', function() {
                if (window.innerWidth < 992 && navbarCollapse.classList.contains('show')) {
                    navbarToggler.click();
                }
            });
        });
    }
});