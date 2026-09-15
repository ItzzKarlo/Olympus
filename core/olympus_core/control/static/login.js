'use strict';
document.querySelector('#login').addEventListener('submit', async event => {
  event.preventDefault();
  const message = document.querySelector('#message');
  try {
    const response = await fetch('/api/control/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:event.target.password.value})});
    const result = await response.json();
    event.target.password.value = '';
    if (!result.ok) throw new Error(result.error.message);
    location.replace('/control/');
  } catch (error) { message.textContent = error.message; }
});
