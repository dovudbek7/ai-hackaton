// Main App Logic
document.addEventListener('DOMContentLoaded', () => {
    console.log('AI Hackaton App Loaded');

    // Phone formatting for register page
    const phoneInput = document.getElementById('phone-input');
    if (phoneInput) {
        // Initialize with +998 if empty
        if (!phoneInput.value || phoneInput.value === '') {
            phoneInput.value = '+998 ';
        }

        phoneInput.addEventListener('input', function (e) {
            let value = e.target.value;

            // Remove all non-digits except +
            value = value.replace(/[^\d+]/g, '');

            // Ensure it starts with +998
            if (!value.startsWith('+998')) {
                value = '+998';
            }

            // Get the digits after +998
            let digits = value.slice(4);

            // Limit to 9 digits
            digits = digits.slice(0, 9);

            // Format: +998 XX-XXX-XX-XX
            let formatted = '+998';
            if (digits.length > 0) {
                formatted += ' ' + digits.slice(0, 2);
            }
            if (digits.length > 2) {
                formatted += '-' + digits.slice(2, 5);
            }
            if (digits.length > 5) {
                formatted += '-' + digits.slice(5, 7);
            }
            if (digits.length > 7) {
                formatted += '-' + digits.slice(7, 9);
            }

            e.target.value = formatted;
        });

        // Prevent deleting +998
        phoneInput.addEventListener('keydown', function (e) {
            if (e.key === 'Backspace' || e.key === 'Delete') {
                if (this.selectionStart <= 5) {
                    e.preventDefault();
                }
            }
        });
    }

    // Auto redirect logic for approved profile (Optional if needed in future)
    const approvedRedirectCheck = document.getElementById('approved-redirect-check');
    if (approvedRedirectCheck) {
        setTimeout(() => {
            window.location.href = '/qabul-qilindi/';
        }, 800);
    }

    // Region-to-School dependent select logic
    const regionSelect = document.getElementById('region-select');
    const schoolSelect = document.getElementById('school-select');
    const regionWarning = document.getElementById('region-warning');
    const warningMessage = document.getElementById('warning-message');
    const submitBtn = document.getElementById('submit-btn');

    if (regionSelect && schoolSelect) {
        regionSelect.addEventListener('change', function () {
            const regionId = this.value;
            const selectedOption = this.options[this.selectedIndex];
            const isOpen = selectedOption.getAttribute('data-open') === 'True';
            const warning = selectedOption.getAttribute('data-warning');

            // Reset school select
            schoolSelect.innerHTML = '<option value="">Yuklanmoqda...</option>';
            schoolSelect.disabled = true;

            // Handle region warning
            if (regionId && !isOpen) {
                // Show warning
                if (warningMessage && regionWarning) {
                    warningMessage.textContent = warning || "Bu hududda qabul tugagan";
                    regionWarning.classList.remove('hidden');
                }
                // Disable submit button
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
                }
                // Clear school select
                schoolSelect.innerHTML = '<option value="">Qabul yopilgan</option>';
                schoolSelect.disabled = true;
            } else if (regionId && isOpen) {
                // Hide warning
                if (regionWarning) {
                    regionWarning.classList.add('hidden');
                }
                // Enable submit button
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                }

                // Fetch schools via AJAX
                fetch(`/api/schools/${regionId}/`)
                    .then(response => response.json())
                    .then(schools => {
                        schoolSelect.innerHTML = '<option value="">Tanlang...</option>';

                        if (schools.length === 0) {
                            schoolSelect.innerHTML = '<option value="">Maktablar topilmadi</option>';
                        } else {
                            schools.forEach(school => {
                                const option = document.createElement('option');
                                option.value = school.id;
                                option.textContent = school.name;
                                schoolSelect.appendChild(option);
                            });
                            schoolSelect.disabled = false;
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching schools:', error);
                        schoolSelect.innerHTML = '<option value="">Xatolik yuz berdi</option>';
                    });
            } else {
                // No region selected
                if (regionWarning) {
                    regionWarning.classList.add('hidden');
                }
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                }
                schoolSelect.innerHTML = '<option value="">Avval hududni tanlang...</option>';
                schoolSelect.disabled = true;
            }
        });
    }
});
