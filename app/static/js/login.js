document.addEventListener("DOMContentLoaded", () => {
    const loginPanel = document.getElementById("login-form");
    const registerPanel = document.getElementById("register-form");
    const tabs = Array.from(document.querySelectorAll(".form-tab"));

    const setFieldError = (input, message) => {
        const shell = input?.closest(".input-shell");
        const error = document.querySelector(`[data-error-for="${input?.name}"]`);

        shell?.classList.toggle("has-error", Boolean(message));
        if (error) {
            error.textContent = message || "";
        }
        input?.setAttribute("aria-invalid", message ? "true" : "false");
    };

    const validateRequired = (input) => {
        if (!input || input.disabled) {
            return true;
        }

        if (!input.value.trim()) {
            setFieldError(input, "Este campo é obrigatório.");
            return false;
        }

        setFieldError(input, "");
        return true;
    };

    window.switchForm = (formType) => {
        const showRegister = formType === "register";

        loginPanel?.classList.toggle("active", !showRegister);
        registerPanel?.classList.toggle("active", showRegister);

        tabs.forEach((tab, index) => {
            const selected = showRegister ? index === 1 : index === 0;
            tab.classList.toggle("active", selected);
            tab.setAttribute("aria-selected", selected ? "true" : "false");
        });

        const targetUrl = showRegister ? "/register" : "/login";
        if (window.location.pathname !== targetUrl) {
            window.history.replaceState({}, "", targetUrl);
        }
    };

    window.togglePassword = (inputId) => {
        const input = document.getElementById(inputId);
        const button = input?.closest(".input-shell")?.querySelector(".password-toggle");
        if (!input) {
            return;
        }

        const visible = input.type === "password";
        input.type = visible ? "text" : "password";
        button?.classList.toggle("is-visible", visible);
        button?.setAttribute("aria-label", visible ? "Ocultar senha" : "Mostrar senha");
        button?.setAttribute("aria-pressed", visible ? "true" : "false");
    };

    window.checkPasswordStrength = () => {
        const passwordInput = document.getElementById("register-password");
        const confirmInput = document.getElementById("register-password-confirm");
        const registerButton = document.getElementById("register-button");
        const lengthCheck = document.getElementById("length-check");

        const password = passwordInput?.value || "";
        const confirmPassword = confirmInput?.value || "";
        const longEnough = password.length >= 10;
        const matches = password && confirmPassword && password === confirmPassword;

        if (lengthCheck) {
            lengthCheck.textContent = longEnough ? "✓" : "○";
            lengthCheck.classList.toggle("complete", longEnough);
            lengthCheck.classList.toggle("incomplete", !longEnough);
        }

        if (confirmInput && confirmPassword) {
            setFieldError(confirmInput, matches ? "" : "As senhas não conferem.");
        }

        if (registerButton) {
            registerButton.disabled = !(longEnough && matches);
        }
    };

    document.querySelectorAll(".login-form").forEach((form) => {
        const requiredInputs = Array.from(form.querySelectorAll("[required]"));
        const submitButton = form.querySelector("button[type='submit']");
        const buttonText = submitButton?.querySelector(".button-text");
        const defaultButtonText = buttonText?.textContent || "";

        requiredInputs.forEach((input) => {
            input.addEventListener("input", () => {
                validateRequired(input);
                if (input.id === "register-password" || input.id === "register-password-confirm") {
                    window.checkPasswordStrength();
                }
            });
            input.addEventListener("blur", () => validateRequired(input));
        });

        form.addEventListener("submit", (event) => {
            const valid = requiredInputs.every(validateRequired);
            if (!valid) {
                event.preventDefault();
                requiredInputs.find((input) => input.getAttribute("aria-invalid") === "true")?.focus();
                return;
            }

            if (submitButton && !submitButton.disabled) {
                submitButton.disabled = true;
                if (buttonText) {
                    buttonText.textContent = defaultButtonText.includes("Criar") ? "Criando..." : "Entrando...";
                }
            }
        });
    });

    window.checkPasswordStrength();
});
