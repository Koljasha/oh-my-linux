## Формирование списков имен файлов на основе шаблонов
https://stepik.org/lesson/Формирование-списков-имен-файлов-на-основе-шаблонов-29563/step/2?course=Основы-Linux&unit=10391

### Звездочка (*)

Звездочка * интерпретируется командной оболочкой как символ для генерации списка имен файлов,
причем сам символ звездочки может преобразовываться в любую комбинацию символов (или даже в строку без символов).
В том случае, если не задано пути к директории для формирования списка имен файлов,
командная оболочка будет использовать имена файлов из текущей директории.
Обратитесь к странице руководства glob(7) для получения дополнительной информации.
(Данный вопрос также рассматривается в теме LPI 1.103.3.)
```
[paul@RHELv4u3 gen]$ ls
file1  file2  file3  File4  File55  FileA  fileab  Fileab  FileAB  fileabc
[paul@RHELv4u3 gen]$ ls File*
File4  File55  FileA  Fileab  FileAB
[paul@RHELv4u3 gen]$ ls file*
file1  file2  file3  fileab  fileabc
[paul@RHELv4u3 gen]$ ls *ile55
File55
[paul@RHELv4u3 gen]$ ls F*ile55
File55
[paul@RHELv4u3 gen]$ ls F*55
File55
[paul@RHELv4u3 gen]$
```

### Знак вопроса (?)

Аналогично звездочке, знак вопроса ? интерпретируется командной оболочкой как символ для генерации списка имен файлов,
причем сам знак вопроса соответствует ровно одному символу имени файла.
```
[paul@RHELv4u3 gen]$ ls
file1  file2  file3  File4  File55  FileA  fileab  Fileab  FileAB  fileabc
[paul@RHELv4u3 gen]$ ls File?
File4  FileA
[paul@RHELv4u3 gen]$ ls Fil?4
File4
[paul@RHELv4u3 gen]$ ls Fil??
File4  FileA
[paul@RHELv4u3 gen]$ ls File??
File55  Fileab  FileAB
[paul@RHELv4u3 gen]$
```

### Квадратные скобки ([])

Открывающаяся квадратная скобка [ интерпретируется командной оболочкой как символ для генерации списка имен файлов,
соответствующий любым из символов, находящихся между символом [ и первым следующим за ним символом ].
Порядок следования символов в списке между скобками не имеет значения.
Каждая пара символов скобок заменяется ровно на один символ.
```
[paul@RHELv4u3 gen]$ ls 
file1  file2  file3  File4  File55  FileA  fileab  Fileab  FileAB  fileabc
[paul@RHELv4u3 gen]$ ls File[5A]
FileA
[paul@RHELv4u3 gen]$ ls File[A5]
FileA
[paul@RHELv4u3 gen]$ ls File[A5][5b]
File55
[paul@RHELv4u3 gen]$ ls File[a5][5b]
File55  Fileab
[paul@RHELv4u3 gen]$ ls File[a5][5b][abcdefghijklm]
ls: невозможно получить доступ к File[a5][5b][abcdefghijklm]: Нет такого файла или каталога
[paul@RHELv4u3 gen]$ ls file[a5][5b][abcdefghijklm]
fileabc
[paul@RHELv4u3 gen]$
```
Также с помощью символа восклицательного знака ! вы можете исключать символы из списка,
расположенного между квадратными скобками.
Кроме того, у вас имеется возможность создания комбинаций из описанных выше шаблонов.
```
[paul@RHELv4u3 gen]$ ls 
file1  file2  file3  File4  File55  FileA  fileab  Fileab  FileAB  fileabc
[paul@RHELv4u3 gen]$ ls file[a5][!Z]
fileab
[paul@RHELv4u3 gen]$ ls file[!5]*
file1  file2  file3  fileab  fileabc
[paul@RHELv4u3 gen]$ ls file[!5]?
fileab
[paul@RHELv4u3 gen]$
```

### Диапазоны a-z и 0-9

Командная оболочка bash также распознает объявления диапазонов символов между квадратными скобками.
```
[paul@RHELv4u3 gen]$ ls
file1  file3  File55  fileab  FileAB   fileabc
file2  File4  FileA   Fileab  fileab2
[paul@RHELv4u3 gen]$ ls file[a-z]*
fileab  fileab2  fileabc
[paul@RHELv4u3 gen]$ ls file[0-9]
file1  file2  file3
[paul@RHELv4u3 gen]$ ls file[a-z][a-z][0-9]*
fileab2
[paul@RHELv4u3 gen]$
```

### Переменная окружения $LANG и квадратные скобки

В ходе работы с командной оболочкой не стоит забывать о влиянии на процесс генерации имен файлов значения переменной окружения LANG.
Причина этого влияния заключается в том, что в некоторых языках строчные буквы включаются в диапазон прописных букв (и наоборот).
```
paul@RHELv4u4:~/test$ ls [A-Z]ile?
file1  file2  file3  File4
paul@RHELv4u4:~/test$ ls [a-z]ile?
file1  file2  file3  File4
paul@RHELv4u4:~/test$ echo $LANG
en_US.UTF-8
paul@RHELv4u4:~/test$ LANG=C
paul@RHELv4u4:~/test$ echo $LANG
C
paul@RHELv4u4:~/test$ ls [a-z]ile?
file1  file2  file3
paul@RHELv4u4:~/test$ ls [A-Z]ile?
File4
paul@RHELv4u4:~/test$
```
В том случае, если в вашей системе устанавливается значение переменной окружения $LC_ALL,
оно также должно быть сброшено для осуществления корректной генерации списков имен файлов.

### Предотвращение формирования списков имен файлов на основе шаблонов

В примере ниже не должно быть ничего удивительного.
При использовании команды echo * в пустой директории будет выведен символ *.
А при использовании той же команды в директории с файлами будут выведены имена всех файлов.
```
paul@ubu1010:~$ mkdir test42
paul@ubu1010:~$ cd test42
paul@ubu1010:~/test42$ echo *
*
paul@ubu1010:~/test42$ touch file42 file33
paul@ubu1010:~/test42$ echo *
file33 file42
```
Формирование списков имен файлов на основе шаблонов может быть предотвращено путем помещения специальных символов в кавычки,
а также экранирования этих символов таким образом, как показано в примере ниже.
```
paul@ubu1010:~/test42$ echo *
file33 file42
paul@ubu1010:~/test42$ echo \*
*
paul@ubu1010:~/test42$ echo '*'
*
paul@ubu1010:~/test42$ echo "*"
*
```
