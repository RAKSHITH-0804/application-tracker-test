document.addEventListener('DOMContentLoaded', () => {
    const signupForm = document.getElementById('signup-form');
    if (!signupForm) return;

    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const errorBox = document.getElementById('error-message');
        const successBox = document.getElementById('success-message');

        errorBox.classList.add('hidden');
        successBox.classList.add('hidden');
        errorBox.innerText = '';
        successBox.innerText = '';

        try {
            const response = await fetch('/auth/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();
            if (response.ok) {
                successBox.innerText = 'Dossier established! Redirecting to login...';
                successBox.classList.remove('hidden');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            } else {
                errorBox.innerText = data.detail || 'Registration failed.';
                errorBox.classList.remove('hidden');
            }
        } catch (err) {
            errorBox.innerText = 'Network error or server unavailable.';
            errorBox.classList.remove('hidden');
        }
    });
});
