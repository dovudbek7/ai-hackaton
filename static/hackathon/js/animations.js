/**
 * Modern AI Hackathon Animations JS
 * Handles scroll detection and dynamic reveals using IntersectionObserver
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!prefersReducedMotion) {
        initScrollReveal();
        initFormAnimations();
    }
});

function initScrollReveal() {
    const options = {
        root: null,
        rootMargin: '0px',
        threshold: 0.15 // Trigger when 15% visible
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                // Optional: Unobserve after revealing to animate only once
                observer.unobserve(entry.target);
            }
        });
    }, options);

    // Observe elements with .reveal-on-scroll class
    const revealElements = document.querySelectorAll('.reveal-on-scroll');
    revealElements.forEach(el => observer.observe(el));

    // Observe stagger containers
    const staggerContainers = document.querySelectorAll('.stagger-container');
    staggerContainers.forEach(el => observer.observe(el));
}

function initFormAnimations() {
    // Add micro-interactions that CSS alone can't handle well or specific logic

    // Example: Add 'input-error' class triggers (if handled via JS validation)
    // This is optional if Django server-side renders errors with the class already.
    // We already have .input-error CSS animation.

    // Smooth scroll for anchors
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if (targetId && targetId !== '#') {
                const target = document.querySelector(targetId);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });
}
