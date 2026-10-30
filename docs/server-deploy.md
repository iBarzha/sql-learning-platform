# Запуск на спільному сервері за хост-nginx

Варіант для сервера, де вже крутяться інші проекти і є свій nginx із сертифікатами.
Платформа займає один порт на 127.0.0.1, хост-nginx термінує TLS і проксує на нього.
Файли: `docker-compose.server.yml`, `nginx/nginx.server.conf`, `server-up.sh`,
`nginx/host-nginx.example.conf`.

## Що робить стек для безпеки

- Назовні лише `127.0.0.1:APP_PORT`. База, бекенд, пісочниці портів не публікують.
- Пісочниці (PostgreSQL, MariaDB, MongoDB, Redis) сидять у внутрішній мережі Docker без
  маршруту в інтернет: навіть зламаний контейнер пісочниці не може нічого завантажити чи
  кудись достукатись. Сховище сесій бекенда живе в окремій внутрішній мережі з паролем,
  тож із пісочниці до нього теж не дістатись.
- Кожен контейнер стартує без Linux capabilities (крім 5 потрібних entrypoint-у офіційних
  образів), з `no-new-privileges`, обмеженням процесів, CPU і пам'яті. Сума лімітів
  пам'яті: 3,4 ГБ. Docker-сокет нікуди не монтується.
- Студентські запити виконує роль `sandbox_student` без прав суперкористувача, тож
  `COPY ... FROM PROGRAM`, `pg_read_file` тощо відмовляє сама СУБД, незалежно від
  валідатора запитів. У MariaDB у студента немає привілею FILE і вимкнено LOCAL INFILE.
  MongoDB запущено без серверного JavaScript (`--noscripting`). У Redis адміністративні
  та скриптові команди перейменовано в порожні, тобто їх не існує.
- Django: `DEBUG=False`, випадковий `SECRET_KEY`, `ALLOWED_HOSTS` лише домен, secure
  cookies і HSTS (`ENABLE_HTTPS=True`), реальна адреса клієнта береться з `X-Real-IP`,
  який ставить ingress, тому ліміти на логін рахуються по користувачу, а не по контейнеру.
- Реєстрації з вулиці немає: користувачів створює адміністратор або запрошення.

## Перший запуск

```bash
sudo mkdir -p /opt/docker/sql_learning
# з робочої машини: git archive <гілка> | ssh <сервер> 'sudo tar xzf - -C /opt/docker/sql_learning'
cd /opt/docker/sql_learning
sudo APP_HOST=sql.example.com APP_PORT=8090 ./server-up.sh
```

Скрипт створює `.env.server` (випадкові паролі, права 600), збирає образи, піднімає стек,
проганяє міграції, створює демо-акаунти та курси (`seed_demo`, `seed_gruber`) і друкує
пароль демо-акаунтів. Усе зберігається у томах проекту `sqlp`.

## Хост-nginx

1. Скопіювати `nginx/host-nginx.example.conf` у `/etc/nginx/sites-available/<домен>`,
   замінити `APP_HOST` і `APP_PORT`, за потреби додати whitelist на `/admin/` і зону
   `limit_req` для логіна.
2. `ln -s` у `sites-enabled`, `nginx -t`, `systemctl reload nginx`.
3. `certbot --nginx -d <домен> --redirect` додасть сертифікат і редирект на HTTPS.

## Оновлення коду

```bash
# з робочої машини
git archive <гілка> | ssh <сервер> 'sudo tar xzf - -C /opt/docker/sql_learning'
ssh <сервер> 'cd /opt/docker/sql_learning && sudo ./server-up.sh --update'
```

`--update` перебирає образи і перезапускає контейнери, дані і секрети лишаються.

## Корисні команди

```bash
cd /opt/docker/sql_learning
C="docker compose --env-file .env.server -f docker-compose.server.yml"
sudo $C ps                       # стан і health
sudo $C logs --tail 100 backend  # логи бекенда
sudo $C exec backend python manage.py seed_gruber --check   # перевірка еталонів курсу
sudo $C down                     # зупинити (дані лишаються)
sudo $C down -v                  # зупинити і видалити дані
```
