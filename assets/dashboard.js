(() => {
  const notice = document.querySelector('#copy-status');
  const dialog = document.querySelector('#copy-dialog');
  let noticeTimer;
  async function copy(value) {
    try {
      await navigator.clipboard.writeText(value);
      notice.textContent = 'Copied to clipboard.';
      clearTimeout(noticeTimer);
      noticeTimer = setTimeout(() => { notice.textContent = ''; }, 3500);
    } catch (_) {
      const text = document.querySelector('#manual-copy');
      text.value = value;
      dialog.showModal();
      text.focus();
      text.select();
    }
  }
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.addEventListener('click', () => copy(button.dataset.copy));
  });
  document.querySelector('#close-copy').addEventListener('click', () => dialog.close());

  document.querySelectorAll('[data-filter]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-filter]').forEach(item => {
        item.setAttribute('aria-pressed', String(item === button));
      });
      let visible = 0;
      document.querySelectorAll('[data-lane-state]').forEach(lane => {
        const state = lane.dataset.laneState;
        lane.hidden = !(button.dataset.filter === 'all'
          || (button.dataset.filter === 'held' && state === 'held')
          || (button.dataset.filter === 'review' && ['stale', 'unknown'].includes(state)));
        if (!lane.hidden) visible += 1;
      });
      document.querySelector('#lane-count').textContent = `${visible} lane${visible === 1 ? '' : 's'}`;
      document.querySelector('#lane-empty').hidden = visible !== 0;
    });
  });
  document.querySelector('#mission-search').addEventListener('input', event => {
    const query = event.target.value.trim().toLowerCase();
    let visible = 0;
    document.querySelectorAll('.mission').forEach(mission => {
      mission.hidden = !mission.dataset.search.includes(query);
      if (!mission.hidden) visible += 1;
    });
    document.querySelector('#mission-empty').hidden = visible !== 0 || !query;
  });

  const form = document.querySelector('#claim-form');
  const lane = document.querySelector('#claim-lane');
  const owner = document.querySelector('#claim-owner');
  const reason = document.querySelector('#claim-reason');
  const ttl = document.querySelector('#claim-ttl');
  const output = document.querySelector('#claim-command');
  const button = document.querySelector('#copy-claim');
  // POSIX shell quoting keeps every value one argument, including quotes,
  // dollar signs, newlines, and command substitutions pasted into the fields.
  function quote(value) { return /^[a-zA-Z0-9_@%+=:,./-]+$/.test(value) ? value : "'" + value.replaceAll("'", "'\"'\"'") + "'"; }
  function updateCommand() {
    const selected = lane.selectedOptions[0];
    const seconds = Number(ttl.value);
    const valid = selected && !selected.disabled && owner.value.trim()
      && reason.value.trim() && ttl.value !== '' && ttl.validity.valid
      && Number.isSafeInteger(seconds) && seconds >= 0;
    button.disabled = !valid;
    output.value = valid ? `${form.dataset.prefix} claim ${quote(lane.value)} ${quote(owner.value)} ${quote(reason.value)} --ttl ${seconds}` : '';
    document.querySelector('#claim-help').textContent = !selected || selected.disabled
      ? 'All lanes are held. Check with their owners and regenerate the snapshot.'
      : !valid ? 'Enter an owner, a reason, and a nonnegative whole number of seconds.'
      : selected.dataset.state === 'stale' ? 'This lease expired. Recheck the previous session before running this command.' : '';
  }
  const options = Array.from(lane.options);
  const available = options.find(option => option.dataset.state === 'clear')
    || options.find(option => !option.disabled);
  if (available) lane.value = available.value;
  form.addEventListener('input', updateCommand);
  form.addEventListener('change', updateCommand);
  form.addEventListener('submit', event => event.preventDefault());
  button.addEventListener('click', () => { if (!button.disabled) copy(output.value); });
  updateCommand();
})();
