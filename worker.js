const USERNAME = "avito";

function unauthorized() {
  return new Response("Доступ к дашборду защищён паролем.", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="Vacancy Review", charset="UTF-8"',
      "Content-Type": "text/plain; charset=UTF-8",
    },
  });
}

function hasAccess(request, password) {
  if (!password) return false;
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Basic ")) return false;

  try {
    const credentials = atob(header.slice(6));
    const separator = credentials.indexOf(":");
    if (separator === -1) return false;
    const username = credentials.slice(0, separator);
    const suppliedPassword = credentials.slice(separator + 1);
    return username === USERNAME && suppliedPassword === password;
  } catch {
    return false;
  }
}

export default {
  async fetch(request, env) {
    // До первого добавления секрета сайт остаётся доступным: это позволяет
    // выложить Worker и затем настроить DASHBOARD_PASSWORD в панели Cloudflare.
    if (!env.DASHBOARD_PASSWORD) return env.ASSETS.fetch(request);
    if (!hasAccess(request, env.DASHBOARD_PASSWORD)) return unauthorized();
    return env.ASSETS.fetch(request);
  },
};
