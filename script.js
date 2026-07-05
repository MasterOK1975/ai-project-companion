// ========== Анимация счётчиков ==========
function animateCounter(element, target, suffix = '') {
    let current = 0;
    const increment = target / 60;
    const interval = setInterval(() => {
        current += increment;
        if (current >= target) {
            current = target;
            clearInterval(interval);
        }
        element.textContent = Math.floor(current) + suffix;
    }, 20);
}

// ========== Intersection Observer для анимаций ==========
const observerOptions = {
    threshold: 0.2,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            
            // Анимация счётчиков в hero
            if (entry.target.classList.contains('hero__stats')) {
                const numbers = entry.target.querySelectorAll('.stat__number');
                animateCounter(numbers[0], 0);
                animateCounter(numbers[1], 100, '%');
                animateCounter(numbers[2], 1);
            }
        }
    });
}, observerOptions);

// Наблюдаем за элементами
document.addEventListener('DOMContentLoaded', () => {
    // Наблюдаем за статистикой
    const stats = document.querySelector('.hero__stats');
    if (stats) observer.observe(stats);

    // Наблюдаем за карточками возможностей
    document.querySelectorAll('.feature-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = `all 0.5s ease ${index * 0.1}s`;
        observer.observe(card);
    });

    // Наблюдаем за шагами
    document.querySelectorAll('.step').forEach((step, index) => {
        step.style.opacity = '0';
        step.style.transform = 'translateY(20px)';
        step.style.transition = `all 0.5s ease ${index * 0.2}s`;
        observer.observe(step);
    });

    // Наблюдаем за карточками тарифов
    document.querySelectorAll('.pricing-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = `all 0.5s ease ${index * 0.15}s`;
        observer.observe(card);
    });
});

// ========== Плавная прокрутка для навигации ==========
document.querySelectorAll('.nav__link, .btn[href]').forEach(link => {
    link.addEventListener('click', (e) => {
        const href = link.getAttribute('href');
        if (href && href.startsWith('#')) {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    });
});

// ========== Эффект параллакса для hero ==========
window.addEventListener('scroll', () => {
    const hero = document.querySelector('.hero');
    if (hero) {
        const scrolled = window.pageYOffset;
        const rate = scrolled * 0.5;
        hero.style.transform = `translateY(${rate * 0.1}px)`;
    }
});

// ========== Анимация появления при скролле (дополнительно) ==========
const style = document.createElement('style');
style.textContent = `
    .feature-card.visible,
    .step.visible,
    .pricing-card.visible {
        opacity: 1 !important;
        transform: translateY(0) !important;
    }
`;
document.head.appendChild(style);

console.log('🧠 AI Project Companion — лендинг загружен');
console.log('📅 Версия 1.0.0');