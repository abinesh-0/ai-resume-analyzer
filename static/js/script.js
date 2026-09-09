document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('resumeInput');
  const name = document.getElementById('fileName');
  if (input && name) input.addEventListener('change', () => { name.textContent = input.files.length ? `✓ ${input.files[0].name}` : ''; });

  const search = document.getElementById('careerSearch');
  const select = document.getElementById('careerSelect');
  if (search && select) search.addEventListener('input', () => {
    const q = search.value.toLowerCase();
    [...select.options].forEach((option, i) => { if (i) option.hidden = !option.text.toLowerCase().includes(q); });
    const current = select.options[select.selectedIndex];
    if (current && current.hidden) select.value = '';
  });

  const resend = document.getElementById('resendBtn');
  const timer = document.getElementById('otpTimer');
  if (resend && timer) {
    let expires = 0;
    const meta = document.querySelector('meta[name="otp-expires"]');
    if (meta) expires = Number(meta.content);
    let busy = false;
    const tick = () => {
      const left = Math.max(0, Math.ceil(expires - Date.now()/1000));
      timer.textContent = `00:${String(left).padStart(2,'0')}`;
      resend.disabled = left > 0;
      resend.style.opacity = left > 0 ? '.55' : '1';
      if (left === 0) timer.textContent = 'OTP expired';
    };
    tick(); setInterval(tick, 1000);
    resend.addEventListener('click', async () => {
      if (busy) return; busy = true;
      const fd = new FormData(); fd.append('purpose', resend.dataset.purpose);
      try {
        const r = await fetch('/resend-otp', {method:'POST', body:fd}); const data = await r.json();
        if (data.success) { expires = Number(data.expires_at); alert(data.message); } else alert(data.message);
      } catch(e) { alert('Unable to resend OTP. Please try again.'); }
      busy = false;
    });
  }
});
