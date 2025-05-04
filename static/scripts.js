document.addEventListener('DOMContentLoaded', function() {
    // === Obsługa zakładek ===
    const tabs = document.querySelectorAll('.sidemenu-item');

    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetId = this.getAttribute('data-tab');

            if (targetId) {
                // Przełącz aktywną zakładkę
                tabs.forEach(btn => btn.classList.remove('active'));
                this.classList.add('active');

                // Ukryj wszystkie treści i pokaż wybraną
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.add('hidden');
                    content.classList.remove('block');
                });

                const target = document.getElementById(targetId);
                if (target) {
                    target.classList.remove('hidden');
                    target.classList.add('block');
                }
            }
        });
    });

    // === Funkcja przełączania podmenu ===
    function toggleSubmenu(button) {
        const submenu = button.nextElementSibling;
        if (submenu && submenu.classList.contains('submenu')) {
            submenu.classList.toggle('open'); // Przełącz klasę open
            button.classList.toggle('open'); // Przełącz klasę dla strzałki
            // Ustaw styl display w zależności od stanu
            submenu.style.display = submenu.classList.contains('open') ? 'block' : 'none';
        }
    }

    // Przyłącz funkcję toggleSubmenu do elementów (np. przycisków z klasą .submenu-toggle)
    document.querySelectorAll('.submenu-toggle').forEach(button => {
        button.addEventListener('click', () => toggleSubmenu(button));
    });

    // === Obsługa formularza audytu ===
    const auditForm = document.getElementById('auditForm');
    if (auditForm) {
        const auditButton = document.getElementById('auditButton');
        const loadingDiv = document.getElementById('loading');
        const urlInput = document.getElementById('url');

        if (auditButton && loadingDiv && urlInput) {
            // Inicjalne ukrycie loadingDiv
            loadingDiv.classList.add('hidden');
            loadingDiv.style.display = 'none';

            auditForm.addEventListener('submit', async function(event) {
                event.preventDefault();

                const url = urlInput.value.trim();
                if (!url) {
                    alert('Proszę wprowadzić adres URL.');
                    return;
                }

                // Pokaż loader, ukryj przycisk
                loadingDiv.classList.remove('hidden');
                loadingDiv.style.display = 'flex';
                auditButton.classList.add('hidden');

                try {
                    // TODO: Zweryfikuj poprawny endpoint API (np. '/audit' zamiast '/')
                    // Sprawdź dokumentację API dla https://onpageiq.online/
                    const response = await fetch('/', {
                        method: 'POST',
                        headers: {
                            // Ustaw Content-Type na podstawie wymagań serwera
                            // Jeśli serwer wymaga application/json, zmień na:
                            // 'Content-Type': 'application/json'
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        // Jeśli używasz application/json, zmień body na:
                        // body: JSON.stringify({ url })
                        body: `url=${encodeURIComponent(url)}`
                    });

                    const data = await response.json();

                    if (response.ok && data.status === 'success') {
                        // Przekierowanie po krótkim opóźnieniu
                        setTimeout(() => {
                            window.location.href = '/report';
                        }, 500);
                    } else {
                        throw new Error(data.error || 'Nieznany błąd');
                    }
                } catch (error) {
                    console.error('Błąd audytu:', error);
                    alert(`Błąd: ${error.message}`);
                } finally {
                    // Przywróć stan początkowy
                    loadingDiv.classList.add('hidden');
                    loadingDiv.style.display = 'none';
                    auditButton.classList.remove('hidden');
                }
            });
        } else {
            console.error('Brak elementów: auditButton, loadingDiv lub urlInput');
        }
    } else {
        console.error('Brak formularza auditForm');
    }
});