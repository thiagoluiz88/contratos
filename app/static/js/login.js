document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("loginForm");
    const passwordInput = document.getElementById("password");
    const usernameInput = document.getElementById("username");
    const passwordToggle = document.getElementById("passwordToggle");
    const submitButton = document.getElementById("submitButton");

    if (!form || !passwordInput || !usernameInput || !passwordToggle || !submitButton) {
        return;
    }

    const buttonText = submitButton.querySelector(".button-text");

    const setFieldError = (input, message) => {
        const shell = input.closest(".input-shell");
        const error = document.querySelector(`[data-error-for="${input.name}"]`);
        if (shell) {
            shell.classList.toggle("has-error", Boolean(message));
        }
        if (error) {
            error.textContent = message || "";
        }
        input.setAttribute("aria-invalid", message ? "true" : "false");
    };

    const validateField = (input) => {
        const value = input.value.trim();
        if (!value) {
            setFieldError(input, "Este campo é obrigatório.");
            return false;
        }
        setFieldError(input, "");
        return true;
    };

    passwordToggle.addEventListener("click", () => {
        const nextType = passwordInput.type === "password" ? "text" : "password";
        const visible = nextType === "text";
        passwordInput.type = nextType;
        passwordToggle.classList.toggle("is-visible", visible);
        passwordToggle.setAttribute("aria-label", visible ? "Ocultar senha" : "Mostrar senha");
        passwordToggle.setAttribute("aria-pressed", visible ? "true" : "false");
    });

    [usernameInput, passwordInput].forEach((input) => {
        input.addEventListener("input", () => validateField(input));
        input.addEventListener("blur", () => validateField(input));
    });

    form.addEventListener("submit", (event) => {
        const usernameOk = validateField(usernameInput);
        const passwordOk = validateField(passwordInput);

        if (!usernameOk || !passwordOk) {
            event.preventDefault();
            if (!usernameOk) {
                usernameInput.focus();
            } else {
                passwordInput.focus();
            }
            return;
        }

        submitButton.disabled = true;
        if (buttonText) {
            buttonText.textContent = "Entrando...";
        }
    });
});
