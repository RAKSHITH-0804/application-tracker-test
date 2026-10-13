document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (!loginForm) return;

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const errorBox = document.getElementById('error-message');

        errorBox.classList.add('hidden');
        errorBox.innerText = '';

        try {
            const response = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();
            if (response.ok) {
                window.location.href = '/';
            } else {
                errorBox.innerText = data.detail || 'Authentication failed.';
                errorBox.classList.remove('hidden');
            }
        } catch (err) {
            errorBox.innerText = 'Network error or server unavailable.';
            errorBox.classList.remove('hidden');
        }
    });
});
