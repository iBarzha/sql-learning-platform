"""Course built from Martin Gruber, "Mastering SQL" (Sybex, 2000), parts I-III.

    python manage.py seed_gruber                     create the course (idempotent)
    python manage.py seed_gruber --reset             delete and recreate it
    python manage.py seed_gruber --check             grade every reference answer on its own
                                                     datasets through the real sandbox
    python manage.py seed_gruber --instructor x@y    owner (default instructor@test.com)

The schema, data and exercises are the book's own ("Putting SQL to Work" with the
answers of Appendix A); theory is a short Ukrainian summary of each chapter.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.models import Course, Dataset, Lesson, LessonExercise, Module
from users.models import User

COURSE_CODE = 'GRUBER'
DB_TYPE = 'postgresql'

SCHEMA = """CREATE TABLE Salespeople (
  snum  INTEGER PRIMARY KEY,
  sname VARCHAR(15),
  city  VARCHAR(15),
  comm  DECIMAL(4,2)
);

CREATE TABLE Customers (
  cnum   INTEGER PRIMARY KEY,
  cname  VARCHAR(15),
  city   VARCHAR(15),
  rating INTEGER,
  snum   INTEGER REFERENCES Salespeople(snum)
);

CREATE TABLE Orders (
  onum  INTEGER PRIMARY KEY,
  amt   DECIMAL(7,2),
  odate DATE,
  cnum  INTEGER REFERENCES Customers(cnum),
  snum  INTEGER REFERENCES Salespeople(snum)
);"""

SALESPEOPLE = [
    (1001, 'Peel', 'London', .12),
    (1002, 'Serres', 'San Jose', .13),
    (1004, 'Motika', 'London', .11),
    (1007, 'Rifkin', 'Barcelona', .15),
    (1003, 'Axelrod', 'New York', .10),
]
CUSTOMERS = [
    (2001, 'Hoffman', 'London', 100, 1001),
    (2002, 'Giovanni', 'Rome', 200, 1003),
    (2003, 'Liu', 'San Jose', 200, 1002),
    (2004, 'Grass', 'Berlin', 300, 1002),
    (2006, 'Clemens', 'London', None, 1001),
    (2008, 'Cisneros', 'San Jose', 300, 1007),
    (2007, 'Pereira', 'Rome', 100, 1004),
]
ORDERS = [
    (3001, 18.69, '2000-10-03', 2008, 1007),
    (3003, 767.19, '2000-10-03', 2001, 1001),
    (3002, 1900.10, '2000-10-03', 2007, 1004),
    (3005, 5160.45, '2000-10-03', 2003, 1002),
    (3006, 1098.16, '2000-10-03', 2008, 1007),
    (3009, 1713.23, '2000-10-04', 2002, 1003),
    (3007, 75.75, '2000-10-04', 2004, 1002),
    (3008, 4723.00, '2000-10-05', 2006, 1001),
    (3010, 1309.95, '2000-10-06', 2004, 1002),
    (3011, 9891.88, '2000-10-06', 2006, 1001),
]


def _lit(value):
    if value is None:
        return 'NULL'
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    return "'" + str(value).replace("'", "''") + "'"


def seed_sql(salespeople=(), customers=(), orders=()):
    def rows(items):
        return ',\n'.join('  (' + ', '.join(_lit(v) for v in item) + ')' for item in items)
    return (
        'INSERT INTO Salespeople (snum, sname, city, comm) VALUES\n'
        + rows(list(SALESPEOPLE) + list(salespeople)) + ';\n\n'
        'INSERT INTO Customers (cnum, cname, city, rating, snum) VALUES\n'
        + rows(list(CUSTOMERS) + list(customers)) + ';\n\n'
        'INSERT INTO Orders (onum, amt, odate, cnum, snum) VALUES\n'
        + rows(list(ORDERS) + list(orders)) + ';'
    )


# Hidden datasets. Each adds the rows the visible data lacks for one kind of mistake.
NO_ORDERS = {
    'name': 'Без замовлень',
    'targets': 'продавець без клієнтів і клієнт без замовлень',
    'seed_sql': seed_sql(salespeople=[(1005, 'Fisher', 'Dublin', .10)],
                         customers=[(2010, 'Jacobs', 'Paris', 200, 1001)]),
}
BOUNDARIES = {
    'name': 'Граничні значення',
    'targets': 'замовлення рівно на 1000.00, комісія рівно .12, рейтинг рівно 200, імя з малої літери',
    'seed_sql': seed_sql(salespeople=[(1008, 'Lowe', 'Berlin', .12)],
                         customers=[(2011, 'cobb', 'Berlin', 200, 1008)],
                         orders=[(3012, 1000.00, '2000-10-04', 2011, 1008)]),
}
NULLS = {
    'name': 'NULL-и',
    'targets': 'клієнт без рейтингу в Римі, продавець без комісії, замовлення без суми',
    'seed_sql': seed_sql(salespeople=[(1009, 'Blanco', 'San Jose', None)],
                         customers=[(2012, 'Nunes', 'Rome', None, 1009)],
                         orders=[(3013, None, '2000-10-05', 2012, 1009)]),
}
DUPLICATES = {
    'name': 'Повтори',
    'targets': 'два клієнти з однаковим найбільшим рейтингом в одному місті, два однакові замовлення',
    'seed_sql': seed_sql(customers=[(2013, 'Doyle', 'London', 100, 1004)],
                         orders=[(3014, 767.19, '2000-10-03', 2013, 1004),
                                 (3015, 767.19, '2000-10-03', 2013, 1004)]),
}

LOCAL_PLAYGROUND = (
    '```sql-exercise\n'
    '{"schema":"CREATE TABLE Salespeople(snum INTEGER, sname TEXT, city TEXT, comm REAL);'
    'CREATE TABLE Customers(cnum INTEGER, cname TEXT, city TEXT, rating INTEGER, snum INTEGER);'
    'CREATE TABLE Orders(onum INTEGER, amt REAL, odate TEXT, cnum INTEGER, snum INTEGER);",'
    '"seed":"INSERT INTO Salespeople VALUES (1001,\'Peel\',\'London\',0.12),(1002,\'Serres\',\'San Jose\',0.13),'
    '(1004,\'Motika\',\'London\',0.11),(1007,\'Rifkin\',\'Barcelona\',0.15),(1003,\'Axelrod\',\'New York\',0.10);'
    'INSERT INTO Customers VALUES (2001,\'Hoffman\',\'London\',100,1001),(2002,\'Giovanni\',\'Rome\',200,1003),'
    '(2003,\'Liu\',\'San Jose\',200,1002),(2004,\'Grass\',\'Berlin\',300,1002),(2006,\'Clemens\',\'London\',NULL,1001),'
    '(2008,\'Cisneros\',\'San Jose\',300,1007),(2007,\'Pereira\',\'Rome\',100,1004);'
    'INSERT INTO Orders VALUES (3001,18.69,\'2000-10-03\',2008,1007),(3003,767.19,\'2000-10-03\',2001,1001),'
    '(3002,1900.10,\'2000-10-03\',2007,1004),(3005,5160.45,\'2000-10-03\',2003,1002),(3006,1098.16,\'2000-10-03\',2008,1007),'
    '(3009,1713.23,\'2000-10-04\',2002,1003),(3007,75.75,\'2000-10-04\',2004,1002),(3008,4723.00,\'2000-10-05\',2006,1001),'
    '(3010,1309.95,\'2000-10-06\',2004,1002),(3011,9891.88,\'2000-10-06\',2006,1001);",'
    '"initial":"SELECT * FROM Customers WHERE city = \'London\';",'
    '"hint":"Спробуйте SELECT sname, comm FROM Salespeople ORDER BY comm DESC"}\n'
    '```'
)

# ── theory ───────────────────────────────────────────────────────────────────

THEORY_INTRO = """# Розділи 1–2. Реляційні бази даних і мова SQL

Книга Мартіна Грубера працює з трьома таблицями фірми, що продає товари через продавців:

| Таблиця | Що зберігає | Ключ |
|---|---|---|
| `Salespeople` | продавці: номер `snum`, імя `sname`, місто `city`, комісія `comm` | `snum` |
| `Customers` | клієнти: `cnum`, `cname`, `city`, рейтинг `rating`, продавець `snum` | `cnum` |
| `Orders` | замовлення: `onum`, сума `amt`, дата `odate`, клієнт `cnum`, продавець `snum` | `onum` |

Кожен клієнт закріплений за одним продавцем (`Customers.snum` посилається на `Salespeople.snum`),
кожне замовлення належить клієнту і продавцю. Такі посилання називають зовнішніми ключами:
значення у стовпці-посиланні має існувати в таблиці, на яку воно вказує.

Рядки таблиці не мають порядку. Якщо потрібен порядок у відповіді, його задають явно (`ORDER BY`).

## Три групи команд SQL

1. DDL, визначення даних: `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`, `CREATE VIEW`.
2. DML, робота з даними: `SELECT`, `INSERT`, `UPDATE`, `DELETE`.
3. DCL, керування доступом: `GRANT`, `REVOKE`.

Регістр ключових слів не важливий, рядкові значення беруться в одинарні лапки,
інструкція закінчується крапкою з комою.

## Спробуйте

Таблиці з книги прямо тут, у браузері. Запит нижче можна змінювати.

""" + LOCAL_PLAYGROUND + """

Далі в курсі всі практичні завдання виконуються на PostgreSQL із цими самими таблицями
і даними з книги.
"""

THEORY_DDL = """# Розділи 3–5. Створення таблиць і обмеження

Таблицю створює `CREATE TABLE`: назва, стовпці, тип кожного стовпця.

```sql
CREATE TABLE Salespeople (
  snum  INTEGER NOT NULL PRIMARY KEY,
  sname CHAR(15),
  city  CHAR(15),
  comm  DECIMAL NOT NULL DEFAULT .10
);
```

Основні типи з книги: `INTEGER`, `DECIMAL(p, s)`, `CHAR(n)` і `VARCHAR(n)`, `DATE`.

## Обмеження

| Обмеження | Що гарантує |
|---|---|
| `NOT NULL` | у стовпці не буде порожніх значень |
| `UNIQUE` | значення не повторюються |
| `PRIMARY KEY` | унікальний і не NULL ідентифікатор рядка; один на таблицю |
| `CHECK (умова)` | кожен рядок задовольняє умову, наприклад `CHECK (comm < 1)` |
| `DEFAULT` | значення, яке підставляється, коли його не вказали |
| `FOREIGN KEY ... REFERENCES` | значення існує в іншій таблиці (батьківський ключ) |

Зовнішній ключ у книзі задається так:

```sql
CREATE TABLE Customers (
  cnum   INTEGER NOT NULL PRIMARY KEY,
  cname  CHAR(15),
  city   CHAR(15),
  rating INTEGER,
  snum   INTEGER,
  FOREIGN KEY (snum) REFERENCES Salespeople (snum)
);
```

Після цього не можна додати клієнта з номером продавця, якого немає, і не можна
видалити продавця, поки на нього посилаються клієнти (якщо не задано `ON DELETE CASCADE`).

`ALTER TABLE ... ADD COLUMN` і `DROP COLUMN` змінюють таблицю, `DROP TABLE` її видаляє.

У нашому курсі таблиці вже створені. Наступний урок про те, як наповнювати їх даними.
"""

THEORY_DML = """# Розділ 6. INSERT, UPDATE, DELETE

Три інструкції змінюють вміст таблиць.

```sql
INSERT INTO Salespeople (snum, sname, city, comm)
VALUES (1009, 'Blanco', 'San Jose', NULL);

UPDATE Customers SET rating = rating + 50 WHERE city = 'London';

DELETE FROM Orders WHERE onum = 3001;
```

- В `INSERT` список стовпців можна задати у будь-якому порядку; значення йдуть у тому ж порядку.
  Стовпці, яких немає у списку, отримують `DEFAULT` або `NULL`.
- `UPDATE` і `DELETE` без `WHERE` зачіпають усі рядки таблиці.
- `INSERT ... SELECT` переносить набір рядків з одного запиту в таблицю.

## Як перевіряються такі завдання

Платформа виконує ваш запит і еталонний на окремих копіях даних, а потім порівнює
вміст таблиць після виконання. Тому зараховується будь-яка інструкція, після якої
таблиці виглядають так само, як після еталонної.
"""

THEORY_SELECT = """# Розділ 7. Вибірка даних: SELECT і WHERE

```sql
SELECT snum, sname, city, comm
FROM Salespeople;
```

- `SELECT *` виводить усі стовпці; список стовпців задає їх порядок у відповіді.
- `SELECT DISTINCT snum FROM Orders` прибирає повтори.
- `WHERE` залишає рядки, для яких умова істинна.

Оператори порівняння: `=`, `<>`, `<`, `>`, `<=`, `>=`. Логічні: `AND`, `OR`, `NOT`.
`NOT` застосовується до того, що йде одразу після нього, а дужки задають порядок обчислення:

```sql
SELECT * FROM Customers
WHERE NOT (rating <= 100 AND city <> 'Rome');
```

Умова з `NULL` не є ні істинною, ні хибною. Рядок із `rating = NULL` не потрапить
ні в `rating > 100`, ні в `NOT rating > 100`.
"""

THEORY_PREDICATES = """# Розділ 8. IN, BETWEEN, LIKE, IS NULL і агрегатні функції

```sql
SELECT * FROM Orders WHERE odate IN ('2000-10-03', '2000-10-04');
SELECT * FROM Orders WHERE amt BETWEEN 1000 AND 5000;      -- межі включно
SELECT * FROM Customers WHERE cname LIKE 'G%';              -- % будь-який рядок, _ один символ
SELECT * FROM Customers WHERE rating IS NULL;               -- тільки так, не = NULL
```

Дати у книзі записані як `10/03/2000`; у PostgreSQL надійніше писати `'2000-10-03'`.

## Агрегатні функції

`COUNT`, `SUM`, `AVG`, `MAX`, `MIN` обчислюють одне значення для групи рядків.
`COUNT(*)` рахує рядки, `COUNT(DISTINCT city)` різні значення, `NULL` ігнорується.

```sql
SELECT snum, MAX(amt)
FROM Orders
GROUP BY snum
HAVING MAX(amt) > 3000;
```

- `GROUP BY` ділить рядки на групи, агрегат рахується для кожної.
- У `SELECT` поряд з агрегатом можуть бути лише стовпці з `GROUP BY`.
- `HAVING` фільтрує групи, `WHERE` фільтрує рядки до групування.
"""

THEORY_EXPRESSIONS = """# Розділ 9. Вирази, константи, CASE, ORDER BY

У списку `SELECT` можуть бути не лише стовпці, а й вирази:

```sql
SELECT onum, amt * .12 FROM Orders;
SELECT 'Продавець', sname, 'з міста', city FROM Salespeople;
```

`CASE` обирає значення за умовою:

```sql
SELECT cnum, cname,
       CASE city WHEN 'London' THEN 'Brussels' ELSE city END
FROM Customers;
```

`COALESCE(rating, 0)` повертає перше не-NULL значення зі списку.

## Сортування

```sql
SELECT odate, SUM(amt)
FROM Orders
GROUP BY odate
ORDER BY 2 DESC;
```

`ORDER BY` приймає назви стовпців або їх номери у списку `SELECT`;
`DESC` сортує за спаданням, за замовчуванням `ASC`.
У завданнях, де порядок задано умовою, він перевіряється.
"""

THEORY_JOINS = """# Розділ 10. Запити до кількох таблиць

Таблиці зєднують, перелічивши їх у `FROM` і вказавши умову відповідності рядків:

```sql
SELECT onum, cname
FROM Orders, Customers
WHERE Customers.cnum = Orders.cnum;
```

Те саме сучасним синтаксисом:

```sql
SELECT onum, cname
FROM Orders JOIN Customers ON Customers.cnum = Orders.cnum;
```

Стовпець, що є в обох таблицях, уточнюють назвою таблиці або псевдонімом (`Orders.cnum`).

## Зєднання таблиці з собою

Псевдоніми дозволяють взяти одну таблицю двічі:

```sql
SELECT a.sname, b.sname
FROM Salespeople a, Salespeople b
WHERE a.city = b.city AND a.sname < b.sname;
```

Умова `a.sname < b.sname` прибирає пари продавця з самим собою і дзеркальні повтори.

`LEFT OUTER JOIN` зберігає рядки лівої таблиці, для яких пари не знайшлося.
"""

THEORY_SUBQUERIES = """# Розділ 11. Підзапити

Запит можна вкласти в умову іншого запиту:

```sql
SELECT * FROM Orders
WHERE cnum = (SELECT cnum FROM Customers WHERE cname = 'Cisneros');
```

- Якщо підзапит повертає одне значення, його порівнюють як звичайне.
- Якщо кілька, використовують `IN`.
- Підзапит з агрегатом (`SELECT AVG(amt) FROM Orders`) завжди повертає одне значення.
- Підзапити працюють і в `HAVING`.

## Корельований підзапит

Внутрішній запит посилається на рядок зовнішнього і виконується для кожного такого рядка:

```sql
SELECT cnum, cname
FROM Customers o
WHERE rating = (SELECT MAX(rating) FROM Customers i WHERE i.city = o.city);
```
"""

THEORY_OPERATORS = """# Розділ 12. EXISTS, ANY, ALL

`EXISTS` істинний, якщо підзапит повернув хоча б один рядок. Найчастіше з корельованим підзапитом:

```sql
SELECT * FROM Salespeople a
WHERE EXISTS (SELECT * FROM Customers b WHERE a.snum = b.snum AND rating = 300);
```

`ANY` (синонім `SOME`) і `ALL` порівнюють значення з усім результатом підзапиту:

```sql
SELECT * FROM Customers
WHERE rating >= ANY (SELECT rating FROM Customers WHERE snum = 1002);

SELECT * FROM Orders
WHERE amt > ALL (SELECT amt FROM Orders a, Customers b
                 WHERE a.cnum = b.cnum AND b.city = 'London');
```

Пастки, про які попереджає книга:

- `<> ALL` означає «не дорівнює жодному», а `<> ANY` майже завжди істинний.
- Якщо підзапит повернув порожній результат, `ALL` істинний для всіх рядків, `ANY` хибний.
- `NULL` у результаті підзапиту робить порівняння невизначеним.
"""

THEORY_SETS = """# Розділ 13. Обєднання запитів

`UNION` зливає результати двох запитів в один, прибираючи повтори; `UNION ALL` їх зберігає.
Запити мають повертати однакову кількість стовпців сумісних типів.

```sql
SELECT snum, sname FROM Salespeople WHERE city = 'London'
UNION
SELECT cnum, cname FROM Customers WHERE city = 'London';
```

`ORDER BY` можна дописати лише один раз, у кінці, за номером стовпця.

`INTERSECT` залишає спільні рядки, `EXCEPT` рядки першого запиту, яких немає в другому:

```sql
SELECT snum FROM Salespeople WHERE city = 'London'
INTERSECT
SELECT snum FROM Customers WHERE city = 'London';
```

Константний стовпець у кожній частині обєднання підписує, звідки прийшов рядок.
"""

THEORY_VIEWS = """# Розділи 14–15. Подання

Подання (view) це збережений запит, до якого звертаються як до таблиці:

```sql
CREATE VIEW Londonstaff AS
  SELECT * FROM Salespeople WHERE city = 'London';

SELECT * FROM Londonstaff;
```

Подання не зберігає даних: щоразу виконується його запит. Стовпцям можна дати
власні назви: `CREATE VIEW Salescount(city, salesperson_count) AS SELECT city, COUNT(snum) ...`.

## Зміна даних через подання

`INSERT`, `UPDATE`, `DELETE` через подання переходять на базову таблицю, але не для будь-якого подання.
Подання не можна оновлювати, якщо в ньому є `DISTINCT`, агрегати, `GROUP BY`, зєднання
кількох таблиць або воно побудоване на такому поданні.

`WITH CHECK OPTION` забороняє через подання вносити рядки, які в нього не потрапили б:

```sql
CREATE VIEW Commissions AS
  SELECT snum, comm FROM Salespeople WHERE comm BETWEEN .10 AND .20
WITH CHECK OPTION;
```

У практиці до цього уроку перевіряється вміст створеного подання: назвіть його так,
як сказано в завданні.
"""

THEORY_ADMIN = """# Розділи 16–18. Права, транзакції, цілісність

## Права доступу

```sql
GRANT SELECT, UPDATE (rating) ON Customers TO Janet;
GRANT SELECT ON Orders TO Stephen WITH GRANT OPTION;
REVOKE INSERT ON Salespeople FROM Claire CASCADE;
```

Права видають на таблицю або окремі стовпці; `WITH GRANT OPTION` дозволяє передавати їх далі;
`REVOKE ... CASCADE` забирає і передані права. Обмежити видимі рядки допомагає подання:
дати право на подання `WHERE rating = (SELECT MIN(rating) FROM Customers)`, а не на таблицю.

Пісочниця курсу навмисно не виконує `GRANT` і `REVOKE`: у ній кожен працює у власній копії даних.

## Транзакції

Група інструкцій виконується як одне ціле: `COMMIT` робить зміни постійними, `ROLLBACK`
скасовує все з початку транзакції. Після збою живлення незавершена транзакція відкочується.

Проблеми одночасної роботи, які описує книга:

- неповторюване читання: між двома `SELECT AVG(rating)` інша транзакція змінила рядки;
- фантомна вставка: між двома читаннями зявився новий рядок;
- блокування: ексклюзивне (X) не дає читати рядок, спільне (S) лише змінювати;
  блокування окремого рядка обмежує інших найменше.

## Системний каталог

СУБД зберігає опис своїх таблиць, стовпців і прав у власних таблицях, це метадані.
До них можна робити лише `SELECT`, і видно тільки ті обєкти, на які є хоч одне право.
У SQL92 це `INFORMATION_SCHEMA`.
"""

THEORY_TEST = """# Контрольна робота

П'ять завдань за розділами 7–13, по 20 балів. На все відведено **30 хвилин** від моменту,
коли ви відкриєте практичну частину; на кожне завдання **3 спроби**, зараховується найкраща.
Кожне завдання перевіряється і на прихованих даних, тому відповідь має працювати не лише
на таблицях з книги.
"""


def ex(title, description, query, *, hidden=(), required=(), forbidden=(), hints=(), max_score=100):
    return dict(
        title=title, description=description, expected_query=query,
        check_datasets=[dict(h) for h in hidden],
        required_keywords=list(required), forbidden_keywords=list(forbidden),
        hints=list(hints), max_score=max_score,
    )


def lessons():
    """(module, lesson fields, exercises) in course order."""
    return [
        ('Частина I. Основи', dict(
            title='Реляційні бази даних і мова SQL', lesson_type='theory',
            description='Розділи 1–2: таблиці Salespeople, Customers, Orders, ключі, групи команд',
            theory_content=THEORY_INTRO), []),
        ('Частина I. Основи', dict(
            title='Створення таблиць і обмеження', lesson_type='theory',
            description='Розділи 3–5: CREATE TABLE, типи, NOT NULL, UNIQUE, PRIMARY KEY, FOREIGN KEY',
            theory_content=THEORY_DDL), []),
        ('Частина I. Основи', dict(
            title='INSERT, UPDATE, DELETE', lesson_type='mixed',
            description='Розділ 6: зміна даних',
            theory_content=THEORY_DML), [
            ex('Новий продавець',
               'Додайте до таблиці Salespeople продавця: місто San Jose, імя Blanco, '
               'комісія NULL, номер 1100.',
               "INSERT INTO Salespeople (city, sname, comm, snum) VALUES ('San Jose', 'Blanco', NULL, 1100)",
               hints=['Порядок значень у VALUES має відповідати списку стовпців після назви таблиці.']),
            ex('Замовлення клієнта Clemens',
               'Видаліть з таблиці Orders усі замовлення клієнта Clemens.',
               "DELETE FROM Orders WHERE cnum = (SELECT cnum FROM Customers WHERE cname = 'Clemens')",
               hints=['Номер клієнта Clemens можна знайти підзапитом до Customers.']),
            ex('Рейтинг клієнтів Рима',
               'Збільште рейтинг усіх клієнтів з Рима на 100.',
               "UPDATE Customers SET rating = rating + 100 WHERE city = 'Rome'"),
            ex('Продавець Serres звільнилась',
               'Serres (номер 1002) залишила фірму. Передайте її клієнтів продавцю Motika (1004).',
               'UPDATE Customers SET snum = 1004 WHERE snum = 1002'),
        ]),
        ('Частина II. Запити', dict(
            title='Вибірка даних: SELECT і WHERE', lesson_type='mixed',
            description='Розділ 7: стовпці, DISTINCT, умови, логічні оператори',
            theory_content=THEORY_SELECT), [
            ex('Три стовпці замовлень',
               'Виведіть номер, суму і дату для всіх рядків таблиці Orders.',
               'SELECT onum, amt, odate FROM Orders'),
            ex('Клієнти продавця 1001',
               'Виведіть усі рядки таблиці Customers, у яких номер продавця дорівнює 1001.',
               'SELECT * FROM Customers WHERE snum = 1001', hidden=[NO_ORDERS]),
            ex('Інший порядок стовпців',
               'Виведіть таблицю Salespeople зі стовпцями у такому порядку: city, sname, snum, comm.',
               'SELECT city, sname, snum, comm FROM Salespeople'),
            ex('Продавці із замовленнями',
               'Виведіть номери (snum) усіх продавців, які мають замовлення в таблиці Orders, без повторів.',
               'SELECT DISTINCT snum FROM Orders', hidden=[DUPLICATES],
               hints=['DISTINCT прибирає однакові рядки з результату.']),
            ex('Лондон і комісія понад .10',
               'Виведіть імена та міста всіх продавців з Лондона, чия комісія більша за .10.',
               "SELECT sname, city FROM Salespeople WHERE city = 'London' AND comm > .10",
               hidden=[BOUNDARIES]),
            ex('Рейтинг понад 100 або Рим',
               'Виведіть клієнтів, виключивши тих, у кого рейтинг не більший за 100, '
               'якщо тільки вони не з Рима.',
               "SELECT * FROM Customers WHERE rating > 100 OR city = 'Rome'",
               hidden=[NULLS, BOUNDARIES],
               hints=['Умова «не більший за 100» це rating <= 100; її треба заперечити.']),
            ex('Спростіть запит',
               'Умова `comm >= .12 OR comm < .14` істинна для будь-якої комісії, якщо comm не NULL. '
               'Напишіть простіший запит з тим самим результатом (стовпці snum, sname, city, comm).',
               'SELECT snum, sname, city, comm FROM Salespeople', forbidden=['WHERE'],
               hints=['Якщо умова завжди істинна, WHERE не потрібен.']),
        ]),
        ('Частина II. Запити', dict(
            title='IN, BETWEEN, LIKE, IS NULL і агрегатні функції', lesson_type='mixed',
            description='Розділ 8: спеціальні оператори, COUNT, SUM, AVG, MAX, MIN, GROUP BY, HAVING',
            theory_content=THEORY_PREDICATES), [
            ex('Замовлення 3 та 4 жовтня',
               'Виведіть усі замовлення, зроблені 3 або 4 жовтня 2000 року.',
               "SELECT * FROM Orders WHERE odate IN ('2000-10-03', '2000-10-04')",
               hidden=[BOUNDARIES], hints=['Підійде IN або BETWEEN за датою.']),
            ex('Імена від A до G',
               'Виведіть клієнтів, чиї імена починаються з літер від A до G включно.',
               "SELECT * FROM Customers WHERE cname >= 'A' AND cname < 'H'",
               hints=['Межа «до G включно» означає «менше за H».']),
            ex('Імена на C',
               'Виведіть клієнтів, чиї імена починаються з C, великої або малої.',
               "SELECT * FROM Customers WHERE cname LIKE 'C%' OR cname LIKE 'c%'",
               hidden=[BOUNDARIES]),
            ex('Замовлення з ненульовою сумою',
               'Виведіть усі замовлення, крім тих, у яких сума дорівнює нулю або NULL.',
               'SELECT * FROM Orders WHERE amt <> 0 AND amt IS NOT NULL',
               hidden=[NULLS], hints=['Порівняння з NULL не відфільтрує NULL; потрібен IS NOT NULL.']),
            ex('Кількість замовлень 3 жовтня',
               'Порахуйте кількість замовлень, зроблених 3 жовтня 2000 року.',
               "SELECT COUNT(*) FROM Orders WHERE odate = '2000-10-03'", hidden=[DUPLICATES]),
            ex('Різні міста клієнтів',
               'Порахуйте кількість різних не-NULL значень міста в таблиці Customers.',
               'SELECT COUNT(DISTINCT city) FROM Customers', hidden=[NO_ORDERS]),
            ex('Найменше замовлення клієнта',
               'Для кожного клієнта виведіть його номер і суму його найменшого замовлення.',
               'SELECT cnum, MIN(amt) FROM Orders GROUP BY cnum', hidden=[DUPLICATES]),
            ex('Перший клієнт на G',
               'Виведіть імя першого за алфавітом клієнта, чиє імя починається з G.',
               "SELECT MIN(cname) FROM Customers WHERE cname LIKE 'G%'"),
            ex('Найвищий рейтинг у місті',
               'Для кожного міста виведіть його назву і найвищий рейтинг клієнта в ньому.',
               'SELECT city, MAX(rating) FROM Customers GROUP BY city', hidden=[NULLS, DUPLICATES]),
            ex('Продавці за день',
               'Для кожної дати порахуйте, скільки різних продавців оформили замовлення цього дня.',
               'SELECT odate, COUNT(DISTINCT snum) FROM Orders GROUP BY odate',
               hidden=[DUPLICATES], hints=['Продавець з двома замовленнями за день рахується один раз.']),
        ]),
        ('Частина II. Запити', dict(
            title='Вирази, CASE і сортування', lesson_type='mixed',
            description='Розділ 9: вирази у SELECT, константи, CASE, COALESCE, ORDER BY',
            theory_content=THEORY_EXPRESSIONS), [
            ex('Комісія з кожного замовлення',
               'Вважайте, що комісія кожного продавця 12 відсотків. Для кожного замовлення виведіть '
               'його номер, номер продавця і суму комісії з цього замовлення.',
               'SELECT onum, snum, amt * .12 FROM Orders', hidden=[BOUNDARIES]),
            ex('Найвищий рейтинг з підписом',
               "Для кожного міста виведіть чотири стовпці: текст 'For the city ', назву міста, "
               "текст ', the highest rating is ' і найвищий рейтинг клієнтів у цьому місті.",
               "SELECT 'For the city ', city, ', the highest rating is ', MAX(rating) "
               'FROM Customers GROUP BY city', hidden=[NULLS]),
            ex('Клієнти за спаданням рейтингу',
               'Виведіть клієнтів за спаданням рейтингу. Спочатку стовпець рейтингу, потім імя і номер клієнта.',
               'SELECT rating, cname, cnum FROM Customers ORDER BY rating DESC',
               hints=['Порядок стовпців: rating, cname, cnum.']),
            ex('Суми замовлень за днями',
               'Для кожної дати виведіть дату і загальну суму замовлень, від найбільшої суми до найменшої.',
               'SELECT odate, SUM(amt) FROM Orders GROUP BY odate ORDER BY 2 DESC', hidden=[DUPLICATES]),
            ex('Лондон як Brussels',
               'Виведіть номер, імя і місто кожного клієнта, але для клієнтів з Лондона замість міста '
               "виведіть 'Brussels'.",
               "SELECT cnum, cname, CASE city WHEN 'London' THEN 'Brussels' ELSE city END FROM Customers",
               required=['CASE']),
            ex('Рейтинг плюс 100 з урахуванням NULL',
               'Збільште рейтинг усіх клієнтів на 100. Клієнтам без рейтингу (NULL) встановіть 100.',
               'UPDATE Customers SET rating = COALESCE(rating, 0) + 100',
               hints=['COALESCE(rating, 0) перетворює NULL на 0.']),
        ]),
        ('Частина II. Запити', dict(
            title='Запити до кількох таблиць', lesson_type='mixed',
            description='Розділ 10: зєднання таблиць, псевдоніми, зєднання таблиці з собою',
            theory_content=THEORY_JOINS), [
            ex('Замовлення та імена клієнтів',
               'Для кожного замовлення виведіть його номер і імя клієнта, який його зробив.',
               'SELECT onum, cname FROM Orders, Customers WHERE Customers.cnum = Orders.cnum',
               hidden=[NO_ORDERS]),
            ex('Клієнти продавців з комісією понад 12%',
               'Виведіть клієнтів, яких обслуговують продавці з комісією понад .12: '
               'імя клієнта, імя продавця і його комісію.',
               'SELECT cname, sname, comm FROM Salespeople, Customers '
               'WHERE Salespeople.snum = Customers.snum AND comm > .12',
               hidden=[BOUNDARIES, NO_ORDERS]),
            ex('Комісія із замовлень клієнтів з рейтингом понад 100',
               'Для кожного замовлення клієнта з рейтингом понад 100 виведіть номер замовлення '
               'і суму комісії продавця з нього (comm * amt).',
               'SELECT onum, comm * amt FROM Salespeople, Orders, Customers '
               'WHERE rating > 100 AND Orders.cnum = Customers.cnum AND Orders.snum = Salespeople.snum',
               hidden=[NULLS]),
            ex('Пари продавців з одного міста',
               'Виведіть усі пари продавців, що живуть в одному місті. Без пари продавця з самим собою '
               'і без дзеркальних повторів.',
               'SELECT a.sname, b.sname FROM Salespeople a, Salespeople b '
               'WHERE a.city = b.city AND a.sname < b.sname',
               hidden=[BOUNDARIES], hints=['Візьміть таблицю двічі під різними псевдонімами.']),
            ex('Той самий рейтинг, що у Hoffman',
               'Виведіть імена і міста всіх клієнтів з таким самим рейтингом, як у клієнта Hoffman. '
               'Використайте його номер 2001, а не рейтинг, щоб запит лишився правильним, коли рейтинг зміниться.',
               'SELECT a.cname, a.city FROM Customers a, Customers b WHERE a.rating = b.rating AND b.cnum = 2001',
               hidden=[DUPLICATES], forbidden=['100']),
        ]),
        ('Частина II. Запити', dict(
            title='Підзапити', lesson_type='mixed',
            description='Розділ 11: вкладені запити, IN, агрегати в підзапитах, корельовані підзапити',
            theory_content=THEORY_SUBQUERIES), [
            ex('Замовлення клієнта Cisneros',
               'За допомогою підзапиту виведіть усі замовлення клієнта на імя Cisneros. '
               'Вважайте, що його номер вам невідомий.',
               "SELECT * FROM Orders WHERE cnum IN (SELECT cnum FROM Customers WHERE cname = 'Cisneros')",
               required=['SUBQUERY'], forbidden=['2008']),
            ex('Замовлення вище середнього',
               'Виведіть імена і рейтинги клієнтів, які мають хоча б одне замовлення із сумою вище '
               'середньої по всіх замовленнях. Кожного клієнта один раз.',
               'SELECT DISTINCT cname, rating FROM Customers, Orders '
               'WHERE amt > (SELECT AVG(amt) FROM Orders) AND Orders.cnum = Customers.cnum',
               hidden=[DUPLICATES]),
            ex('Сума більша за найбільше замовлення',
               'Для кожного продавця виведіть його номер і загальну суму замовлень, але тільки якщо '
               'ця сума більша за суму найбільшого замовлення в таблиці.',
               'SELECT snum, SUM(amt) FROM Orders GROUP BY snum HAVING SUM(amt) > (SELECT MAX(amt) FROM Orders)',
               hidden=[BOUNDARIES], required=['HAVING']),
            ex('Максимальний рейтинг у своєму місті',
               'Корельованим підзапитом виведіть номери та імена клієнтів, чий рейтинг дорівнює '
               'найбільшому рейтингу в їхньому місті.',
               'SELECT cnum, cname FROM Customers o '
               'WHERE rating = (SELECT MAX(rating) FROM Customers i WHERE i.city = o.city)',
               hidden=[DUPLICATES, NULLS], required=['SUBQUERY']),
            ex('Чужі клієнти в місті продавця',
               'Виведіть номери та імена продавців, у чиєму місті є клієнти, яких вони не обслуговують. '
               'Кожного продавця один раз.',
               'SELECT DISTINCT a.snum, sname FROM Salespeople a, Customers b '
               'WHERE a.city = b.city AND a.snum <> b.snum',
               hidden=[NO_ORDERS, DUPLICATES]),
        ]),
        ('Частина II. Запити', dict(
            title='EXISTS, ANY, ALL', lesson_type='mixed',
            description='Розділ 12: оператори над підзапитами і їх поведінка з NULL',
            theory_content=THEORY_OPERATORS), [
            ex('Продавці з клієнтами рейтингу 300',
               'За допомогою EXISTS виведіть усіх продавців, які мають клієнтів з рейтингом 300.',
               'SELECT * FROM Salespeople a WHERE EXISTS '
               '(SELECT * FROM Customers b WHERE a.snum = b.snum AND rating = 300)',
               hidden=[DUPLICATES], required=['EXISTS']),
            ex('Те саме зєднанням',
               'Розвяжіть попередню задачу без EXISTS, зєднанням таблиць: номер, імя, місто і комісія '
               'продавця, кожен один раз.',
               'SELECT DISTINCT a.snum, sname, a.city, comm FROM Salespeople a, Customers b '
               'WHERE a.snum = b.snum AND b.rating = 300',
               hidden=[DUPLICATES], forbidden=['EXISTS']),
            ex('Чужі клієнти через EXISTS',
               'За допомогою EXISTS виведіть усіх продавців, у чиєму місті є клієнти, не закріплені за ними.',
               'SELECT * FROM Salespeople a WHERE EXISTS '
               '(SELECT * FROM Customers b WHERE b.city = a.city AND a.snum <> b.snum)',
               hidden=[NO_ORDERS], required=['EXISTS']),
            ex('Продавець з іншим клієнтом у замовленнях',
               'Виведіть клієнтів, закріплених за продавцем, який має в таблиці Orders замовлення '
               'хоча б від одного іншого клієнта.',
               'SELECT * FROM Customers a WHERE EXISTS '
               '(SELECT * FROM Orders b WHERE a.snum = b.snum AND a.cnum <> b.cnum)',
               hidden=[NO_ORDERS]),
            ex('Рейтинг не нижчий за будь-який у Serres',
               'Виведіть клієнтів, чий рейтинг не нижчий за рейтинг хоча б одного клієнта продавця '
               'Serres (номер 1002). Використайте ANY.',
               'SELECT * FROM Customers WHERE rating >= ANY (SELECT rating FROM Customers WHERE snum = 1002)',
               hidden=[NULLS], required=['ANY']),
            ex('Міста без клієнтів',
               'За допомогою ANY або ALL виведіть продавців, у чиєму місті немає жодного клієнта.',
               'SELECT * FROM Salespeople WHERE city <> ALL (SELECT city FROM Customers)',
               hidden=[NO_ORDERS], hints=['<> ALL означає «не дорівнює жодному значенню».']),
            ex('Більше за всі лондонські',
               'Виведіть замовлення, сума яких більша за суму будь-якого замовлення клієнтів з Лондона. '
               'Використайте ALL.',
               'SELECT * FROM Orders WHERE amt > ALL (SELECT amt FROM Orders a, Customers b '
               "WHERE a.cnum = b.cnum AND b.city = 'London')",
               hidden=[BOUNDARIES], required=['ALL']),
            ex('Те саме через MAX',
               'Перепишіть попередній запит через MAX замість ALL.',
               'SELECT * FROM Orders WHERE amt > (SELECT MAX(amt) FROM Orders a, Customers b '
               "WHERE a.cnum = b.cnum AND b.city = 'London')",
               hidden=[BOUNDARIES], required=['MAX'], forbidden=['ALL']),
        ]),
        ('Частина II. Запити', dict(
            title='UNION, INTERSECT, EXCEPT', lesson_type='mixed',
            description='Розділ 13: обєднання результатів кількох запитів',
            theory_content=THEORY_SETS), [
            ex('High Rating / Low Rating',
               "Обєднанням двох запитів виведіть імя, місто і рейтинг кожного клієнта та підпис: "
               "'High Rating' для рейтингу 200 і більше, 'Low Rating' для решти. NULL вважається низьким.",
               "SELECT cname, city, rating, 'High Rating' FROM Customers WHERE rating >= 200 "
               "UNION SELECT cname, city, rating, 'Low Rating' FROM Customers WHERE rating < 200 OR rating IS NULL",
               hidden=[NULLS, BOUNDARIES], required=['UNION']),
            ex('Більше одного замовлення',
               'Виведіть номер і імя кожного продавця та кожного клієнта, які мають більше одного '
               'замовлення. Відсортуйте за імям.',
               'SELECT cnum, cname FROM Customers a WHERE 1 < (SELECT COUNT(*) FROM Orders b WHERE a.cnum = b.cnum) '
               'UNION SELECT snum, sname FROM Salespeople a WHERE 1 < (SELECT COUNT(*) FROM Orders b WHERE a.snum = b.snum) '
               'ORDER BY 2',
               hidden=[NO_ORDERS], required=['UNION']),
            ex('Три запити в одному',
               'Обєднайте три запити: номери продавців із San Jose; номери клієнтів із San Jose; '
               'номери замовлень за 3 жовтня 2000. Повтори між другим і третім запитами збережіть, '
               'повтори з першим приберіть.',
               "SELECT snum FROM Salespeople WHERE city = 'San Jose' UNION "
               "(SELECT cnum FROM Customers WHERE city = 'San Jose' UNION ALL "
               "SELECT onum FROM Orders WHERE odate = '2000-10-03')",
               required=['UNION'], hints=['UNION ALL у дужках зберігає повтори лише між своїми частинами.']),
            ex('Лондонські продавці з лондонськими клієнтами',
               'Виведіть номери та імена продавців, які живуть у Лондоні і мають хоча б одного клієнта в Лондоні.',
               "SELECT snum, sname FROM Salespeople WHERE city = 'London' INTERSECT "
               "SELECT a.snum, sname FROM Customers a, Salespeople b WHERE a.snum = b.snum AND a.city = 'London'",
               hidden=[NO_ORDERS]),
            ex('Замовлення не зі свого міста',
               'Виведіть пари (snum, cnum) для продавців, які мають замовлення понад 1000.00 не від клієнта '
               'зі свого міста. Продавець з кількома такими клієнтами зявиться кілька разів.',
               'SELECT snum, cnum FROM Orders WHERE amt > 1000.00 EXCEPT '
               'SELECT a.snum, cnum FROM Salespeople a, Customers b WHERE a.snum = b.snum AND a.city = b.city',
               hidden=[BOUNDARIES]),
        ]),
        ('Частина III. Подання, права, транзакції', dict(
            title='Подання', lesson_type='mixed',
            description='Розділи 14–15: CREATE VIEW, оновлювані подання, WITH CHECK OPTION',
            theory_content=THEORY_VIEWS), [
            ex('Подання Highratings',
               'Створіть подання Highratings з усіма стовпцями клієнтів, у яких найвищий рейтинг.',
               'CREATE VIEW Highratings AS SELECT cnum, cname, city, rating, snum FROM Customers '
               'WHERE rating = (SELECT MAX(rating) FROM Customers)'),
            ex('Подання Salescount',
               'Створіть подання Salescount зі стовпцями city і salesperson_count: '
               'кількість продавців у кожному місті.',
               'CREATE VIEW Salescount(city, salesperson_count) AS SELECT city, COUNT(snum) '
               'FROM Salespeople GROUP BY city'),
            ex('Подання DailyOrders',
               'Створіть подання DailyOrders: імя продавця, середня і загальна сума його замовлень.',
               'CREATE VIEW DailyOrders(sname, average, total) AS SELECT sname, AVG(amt), SUM(amt) '
               'FROM Salespeople s, Orders o WHERE s.snum = o.snum GROUP BY s.snum, sname'),
            ex('Подання Multicust',
               'Створіть подання Multicust з усіма стовпцями продавців, які мають більше одного клієнта.',
               'CREATE VIEW Multicust AS SELECT * FROM Salespeople a '
               'WHERE 1 < (SELECT COUNT(*) FROM Customers b WHERE a.snum = b.snum)'),
            ex('Подання Commissions',
               'Створіть подання Commissions зі стовпцями snum і comm таблиці Salespeople, у якому видно '
               'лише комісії від .10 до .20, і через яке не можна внести комісію поза цими межами.',
               'CREATE VIEW Commissions AS SELECT snum, comm FROM Salespeople '
               'WHERE comm BETWEEN .10 AND .20 WITH CHECK OPTION',
               hints=['WITH CHECK OPTION у кінці CREATE VIEW.']),
        ]),
        ('Частина III. Подання, права, транзакції', dict(
            title='Права, транзакції, цілісність', lesson_type='theory',
            description='Розділи 16–18: GRANT і REVOKE, COMMIT і ROLLBACK, системний каталог',
            theory_content=THEORY_ADMIN), []),
        ('Контроль', dict(
            title='Контрольна робота', lesson_type='mixed',
            description='30 хвилин, 5 завдань по 20 балів, 3 спроби на завдання',
            theory_content=THEORY_TEST, time_limit_seconds=30 * 60, max_attempts=3), [
            ex('Найвищий рейтинг у кожному місті',
               'Для кожного міста клієнтів виведіть назву міста і найвищий рейтинг у ньому.',
               'SELECT city, MAX(rating) FROM Customers GROUP BY city',
               hidden=[NULLS, DUPLICATES], max_score=20),
            ex('Клієнти продавців з комісією понад .12',
               'Виведіть імя клієнта, імя його продавця і комісію продавця для продавців з комісією понад .12.',
               'SELECT cname, sname, comm FROM Salespeople, Customers '
               'WHERE Salespeople.snum = Customers.snum AND comm > .12',
               hidden=[BOUNDARIES, NO_ORDERS], max_score=20),
            ex('Продавці з сумою понад найбільше замовлення',
               'Виведіть номер продавця і суму його замовлень для тих продавців, чия сума більша '
               'за найбільше замовлення в таблиці.',
               'SELECT snum, SUM(amt) FROM Orders GROUP BY snum HAVING SUM(amt) > (SELECT MAX(amt) FROM Orders)',
               hidden=[BOUNDARIES, DUPLICATES], max_score=20),
            ex('Продавці без клієнтів у своєму місті',
               'Виведіть усі стовпці продавців, у чиєму місті немає жодного клієнта.',
               'SELECT * FROM Salespeople WHERE city <> ALL (SELECT city FROM Customers)',
               hidden=[NO_ORDERS], max_score=20),
            ex('Великі замовлення не зі свого міста',
               'Виведіть пари (snum, cnum) із замовлень понад 1000.00, зроблених не клієнтами '
               'з міста продавця.',
               'SELECT snum, cnum FROM Orders WHERE amt > 1000.00 EXCEPT '
               'SELECT a.snum, cnum FROM Salespeople a, Customers b WHERE a.snum = b.snum AND a.city = b.city',
               hidden=[BOUNDARIES, NO_ORDERS], max_score=20),
        ]),
    ]


class Command(BaseCommand):
    help = 'Create the "Mastering SQL" course from the book of Martin Gruber.'

    def add_arguments(self, parser):
        parser.add_argument('--instructor', default='instructor@test.com')
        parser.add_argument('--reset', action='store_true')
        parser.add_argument('--check', action='store_true',
                            help='Grade every reference answer on its datasets via the sandbox.')

    def handle(self, *args, **options):
        instructor = User.objects.filter(email=options['instructor']).first()
        if instructor is None:
            raise CommandError(f'No user {options["instructor"]}; pass --instructor.')

        if options['reset']:
            deleted, _ = Course.objects.filter(course_code=COURSE_CODE).delete()
            self.stdout.write(f'Removed the previous course ({deleted} rows).')

        course = Course.objects.filter(course_code=COURSE_CODE).first()
        if course is None:
            with transaction.atomic():
                course = self._create(instructor)
            self.stdout.write(self.style.SUCCESS(
                f'Created "{course.title}": {course.lessons.count()} lessons, '
                f'{LessonExercise.objects.filter(lesson__course=course).count()} exercises, '
                f'code {COURSE_CODE}'))
        else:
            self.stdout.write(f'Course already exists (code {COURSE_CODE}); use --reset to rebuild.')

        if options['check']:
            self._check(course)

    def _create(self, instructor):
        course = Course(
            title='Mastering SQL (М. Грубер)',
            description='Курс за книгою Martin Gruber, Mastering SQL (Sybex, 2000): таблиці '
                        'Salespeople, Customers, Orders, вправи «Putting SQL to Work» з розділів 6–15 '
                        'і контрольна робота. База даних PostgreSQL.',
            instructor=instructor, database_type=DB_TYPE, is_published=True,
        )
        course.course_code = COURSE_CODE
        course.save()
        dataset = Dataset.objects.create(
            name='Продажі (Gruber)', description='Salespeople, Customers, Orders з книги',
            course=course, created_by=instructor, database_type=DB_TYPE,
            schema_sql=SCHEMA, seed_sql=seed_sql(), is_default=True,
            quick_start_queries={
                'basicSelect': 'SELECT * FROM Customers WHERE city = \'London\';',
                'groupBy': 'SELECT snum, SUM(amt) FROM Orders GROUP BY snum;',
                'subquery': 'SELECT * FROM Orders WHERE amt > (SELECT AVG(amt) FROM Orders);',
            },
        )
        modules = {}
        for order, (module_title, fields, exercises) in enumerate(lessons()):
            module = modules.get(module_title)
            if module is None:
                module = Module.objects.create(course=course, title=module_title,
                                               order=len(modules), is_published=True)
                modules[module_title] = module
            lesson = Lesson.objects.create(course=course, module=module, order=order,
                                           is_published=True, **fields)
            for index, exercise in enumerate(exercises):
                LessonExercise.objects.create(lesson=lesson, order=index, dataset=dataset, **exercise)
        return course

    def _check(self, course):
        """Every reference answer must pass its own exercise on the real sandbox."""
        from grading.runner import build_task, make_runner, make_sequence_runner
        from grading.service import grade

        failures = 0
        for exercise in LessonExercise.objects.filter(lesson__course=course).select_related('lesson', 'dataset'):
            task = build_task(DB_TYPE, reference_query=exercise.expected_query, dataset=exercise.dataset,
                              check_datasets=exercise.check_datasets,
                              required_keywords=exercise.required_keywords,
                              forbidden_keywords=exercise.forbidden_keywords,
                              max_score=exercise.max_score, criteria=exercise.criteria)
            result = grade(task, exercise.expected_query, make_runner(DB_TYPE, 10),
                           run_sequence=make_sequence_runner(DB_TYPE, 10))
            status = 'ok  ' if result.passed else 'FAIL'
            if not result.passed:
                failures += 1
            self.stdout.write(f'{status} {exercise.lesson.title} / {exercise.title}: '
                              f'{result.feedback["passed_count"]}/{result.feedback["total"]}')
            if not result.passed:
                for item in result.feedback['criteria']:
                    if not item['passed']:
                        self.stdout.write(f'       - {item["name"]}: {item["detail"]}')
        if failures:
            raise CommandError(f'{failures} reference answer(s) do not pass their own exercise.')
        self.stdout.write(self.style.SUCCESS('All reference answers pass.'))
