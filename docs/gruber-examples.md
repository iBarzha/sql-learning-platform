# Приклади з книги Грубера у пісочниці платформи

Усі SQL-інструкції з розділів 2–18 книги Martin Gruber, *Mastering SQL* (Sybex, 2000) витягнуто з текстового шару DjVu і виконано на схемі книги (Salespeople, Customers, Orders) через пісочницю платформи, кожну окремо, на PostgreSQL 15, MariaDB 10.11 і SQLite.

Інструкцій (без повторів): 352. Текст із DjVu містить помилки розпізнавання, тому частина збоїв стосується не СУБД, а джерела.

## Підсумок по розділах

| Розділ | Тема | Інструкцій | PostgreSQL | MariaDB | SQLite |
|---|---|---|---|---|---|
| 2 | SQL: огляд | 5 | 2 | 2 | 3 |
| 3 | Створення таблиць | 4 | 1 | 1 | 1 |
| 4 | Обмеження | 13 | 2 | 2 | 3 |
| 5 | Зовнішні ключі | 17 | 3 | 2 | 3 |
| 6 | INSERT, UPDATE, DELETE | 11 | 4 | 4 | 7 |
| 7 | SELECT і WHERE | 22 | 16 | 18 | 18 |
| 8 | IN, BETWEEN, LIKE, агрегати | 41 | 27 | 26 | 28 |
| 9 | Вирази, CASE, ORDER BY | 23 | 17 | 17 | 17 |
| 10 | З'єднання | 44 | 25 | 25 | 30 |
| 11 | Підзапити | 27 | 15 | 15 | 16 |
| 12 | EXISTS, ANY, ALL | 40 | 17 | 17 | 6 |
| 13 | UNION, INTERSECT, EXCEPT | 26 | 13 | 10 | 13 |
| 14 | Подання | 19 | 6 | 6 | 7 |
| 15 | Зміна даних через подання | 17 | 11 | 11 | 10 |
| 16 | Права доступу | 27 | 3 | 3 | 2 |
| 17 | Транзакції | 15 | 8 | 8 | 7 |
| 18 | Системний каталог | 1 | 1 | 1 | 0 |
| | **Разом** | **352** | **171** | **168** | **171** |

## Чому приклади не виконались на PostgreSQL

| Причина | Інструкцій |
|---|---|
| синтаксис SQL92 або іншого діалекту, який СУБД не приймає | 69 |
| посилається на таблицю/подання, створені в іншому прикладі | 40 |
| інша помилка виконання (порушення ключа, тип даних тощо) | 26 |
| заблоковано валідатором пісочниці (свідомо: GRANT, REVOKE, ролі) | 24 |
| дефект розпізнавання тексту книги (загублені лапки, 0 замість O) | 22 |

### синтаксис SQL92 або іншого діалекту, який СУБД не приймає

- розділ 3: `ALTER TABLE Salespeople ALTER COLUMN city ADD DEFAULT 'London'`  
  syntax error at or near "DEFAULT"
LINE 1: ALTER TABLE Salespeople ALTER COLUMN city ADD DE
- розділ 4: `CREATE TABLE Salestotal (snum, INTEGER NOT NULL, odate, DATE NOT NULL, totamt, DECIMAL, UN`  
  syntax error at or near "NOT"
LINE 1: CREATE TABLE Salestotal (snum, INTEGER NOT NULL, oda
- розділ 4: `CREATE TABLE Salespeople (snum INTEGER PRIMARY KEY, sname CHAR(10) NOT NULL, city CHAR(10)`  
  syntax error at or near "="
LINE 1: ...Y, sname CHAR(10) NOT NULL, city CHAR(10) DEFAULT =
- розділ 5: `CREATE TABLE Customers (cnum INTEGER NOT NULL PRIMARY KEY, cname CHAR(10) NOT NULL, city C`  
  syntax error at or near "Custtosales"
LINE 1: ... rating INTEGER, snum INTEGER, FOREIGN KE
- розділ 5: `CREATE TABLE Orders (onum INTEGER NOT NULL PRIMARY KEY, amt DECIMAL, odate DATE NOT NULL, `  
  syntax error at end of input
LINE 1: ...EY, amt DECIMAL, odate DATE NOT NULL, cnum INTEGER
- розділ 5: `CREATE TABLE Customers (cnum INTEGER NOT NULL PRIMARY KEY, cname CHAR(10) NOT NULL, city C`  
  syntax error at or near "Salespeople"
LINE 1: ...R, snum INTEGER REFERENCES Salespeople, U

### посилається на таблицю/подання, створені в іншому прикладі

- розділ 4: `ALTER TABLE Customers DROP CONSTRAINT LuckyBarcelona`  
  constraint "luckybarcelona" of relation "customers" does not exist
- розділ 5: `ALTER TABLE Orders DROP CONSTRAINT Ordtosales`  
  constraint "ordtosales" of relation "orders" does not exist
- розділ 5: `ALTER TABLE Orders DROP CONSTRAINT Ordtocust`  
  constraint "ordtocust" of relation "orders" does not exist
- розділ 6: `INSERT INTO Londonstaff SELECT * FROM Salespeople WHERE city = 'London'`  
  relation "londonstaff" does not exist
- розділ 6: `INSERT INTO Londonstaff SELECT snum, sname, city, comm * 1.1 FROM Salespeople WHERE city =`  
  relation "londonstaff" does not exist
- розділ 6: `INSERT INTO Daytotals(date, total) SELECT odate, SUM(amt) FROM Orders GROUP BY odate`  
  relation "daytotals" does not exist

### інша помилка виконання (порушення ключа, тип даних тощо)

- розділ 2: `CREATE TABLE Salespeople (snum INTEGER NOT NULL PRIMARY KEY, sname CHAR(15) NOT NULL, city`  
  relation "salespeople" already exists
- розділ 2: `DELETE FROM Salespeople WHERE snum = 1001`  
  update or delete on table "salespeople" violates foreign key constraint "customers_snum_fk
- розділ 3: `CREATE TABLE Salespeople (snum INTEGER, sname CHAR(10), city CHAR(10), comm DECIMAL)`  
  relation "salespeople" already exists
- розділ 4: `CREATE TABLE Salespeople (snum INTEGER NOT NULL, sname CHAR(10) NOT NULL, city CHAR(10), c`  
  relation "salespeople" already exists
- розділ 4: `CREATE TABLE Salespeople (snum INTEGER NOT NULL PRIMARY KEY, sname CHAR(10) NOT NULL, city`  
  relation "salespeople" already exists
- розділ 4: `CREATE TABLE Salespeople (snum INTEGER NOT NULL PRIMARY KEY, sname CHAR(10) NOT NULL UNIQU`  
  relation "salespeople" already exists

### заблоковано валідатором пісочниці (свідомо: GRANT, REVOKE, ролі)

- розділ 3: `GRANT CONNECT TO Chris`  
  Authentication and user management is off limits.
- розділ 8: `SELECT snum, odate, MAX(amt) FROM Orders WHERE MAX(amt) > 3000.00 GROUP BY snum, odate`  
  aggregate functions are not allowed in WHERE
- розділ 16: `GRANT SELECT ON Customers TO Adrian`  
  Authentication and user management is off limits.
- розділ 16: `GRANT INSERT ON Salespeople TO Diane`  
  Authentication and user management is off limits.
- розділ 16: `GRANT SELECT, INSERT ON Orders TO Adrian, Diane`  
  Authentication and user management is off limits.
- розділ 16: `GRANT UPDATE ON Salespeople TO Diane`  
  Authentication and user management is off limits.

### дефект розпізнавання тексту книги (загублені лапки, 0 замість O)

- розділ 2: `INSERT INTO Salespeople VALUES (1001, 'Peel', 'London', .12)`  
  duplicate key value violates unique constraint "salespeople_pkey"
- розділ 4: `CREATE TABLE Salespeople (snum INTEGER NOT NULL PRIMARY KEY, sname CHAR(10) NOT NULL, city`  
  relation "salespeople" already exists
- розділ 6: `INSERT INTO Customers(city, cname, cnum) VALUES('London', 'Hoffman', 2001)`  
  duplicate key value violates unique constraint "customers_pkey"
- розділ 8: `SELECT * FROM Customers WHERE cname BETWEEN 'A' AND 'Ga: ^ CNUM CNAME CI TV 2006 Clemens L`  
  unterminated quoted string at or near "'Ga: ^ CNUM CNAME CI TV 2006 Clemens London 2008 Ci
- розділ 8: `SELECT * FROM Salespeople WHERE NOT city IN ('London', "San Jose') OR city IS NULL`  
  unterminated quoted identifier at or near ""San Jose') OR city IS NULL"
LINE 1: ...T * FRO
- розділ 9: `INSERT INTO Orders (onum, odate, amt, cnum, snum) VALUES (1 + COALESCE(SELECT MAX(onum) FR`  
  syntax error at or near "SELECT"
LINE 1: ...num, odate, amt, cnum, snum) VALUES (1 + COALE

## Працює на PostgreSQL, але не на інших СУБД

### mariadb: 8 інструкцій

- 6 × `SELECT COUNT (DISTINCT snum) FROM Orders`  
  You have an error in your SQL syntax; check the manual that corresponds to your MariaDB server versi
- 1 × `ALTER TABLE Orders DROP COLUMN snum`  
  Cannot drop index 'snum': needed in a foreign key constraint
- 1 × `SELECT snum, odate, MAX(amt) FROM Orders GROUP BY snum, odate HAVING MAX (amt) >`  
  FUNCTION g_e32c2c51def24e0d.MAX does not exist. Check the 'Function Name Parsing and Resolution' sec

### sqlite: 17 інструкцій

- 16 × `SELECT * FROM Salespeople WHERE city = ANY (SELECT city FROM Customers)`  
  near "SELECT": syntax error
- 1 × `SELECT * FROM INFORMATION_SCHEMA.TABLES`  
  no such table: INFORMATION_SCHEMA.TABLES

## Висновки для платформи

- Ядро книги (розділи 6–15: SELECT, предикати, агрегати, з'єднання, підзапити, EXISTS/ANY/ALL, UNION, подання) виконується на PostgreSQL; саме ці розділи стали практикою курсу.
- SQLite не підтримує ANY/ALL (розділ 12) і частину синтаксису подань, тому курс за книгою має працювати на PostgreSQL.
- GRANT/REVOKE (розділ 16) пісочниця блокує навмисно: кожен студент працює у власній копії даних; ці розділи в курсі лишаються теорією.
- Приклади, що посилаються на об'єкти з попередніх прикладів (наприклад, подання з розділу 14), поодинці не виконуються, це очікувано.
- Дати в книзі записані як 10/03/2000; PostgreSQL їх приймає (MDY), у курсі використано ISO-формат.
