-- DROP VIEW IF EXISTS TodosView;
DROP TABLE IF EXISTS Todos;

CREATE TABLE Todos (
    TaskId     INTEGER     PRIMARY KEY
   ,Content    TEXT        NOT NULL
   ,Completed  INTEGER     NOT NULL DEFAULT 0
   ,SourceFileName TEXT
   ,LocalFileName  TEXT
   ,DatTimIns  INTEGER (4) NOT NULL DEFAULT (strftime('%s', DateTime('Now','UTC'))) -- get Now/UTC, convert to local, convert to string/Unix Time, store as Integer(4)
   ,DatTimUpd  INTEGER(4)      NULL
);
/* how to store timestamps as integers https://stackoverflow.com/questions/200309/sqlite-database-default-time-value-now  */
CREATE TRIGGER trgTodosUpd
         AFTER UPDATE OF Content, Completed, LocalFileName -- list columns which should trigger the update
            ON Todos
BEGIN
    UPDATE Todos
       SET DatTimUpd = strftime('%s', DateTime('Now','UTC') )-- same as DatTimIns 
     WHERE TaskId = new.TaskId;
END;

/* convert Unix-Time to DateTime so not every single query needs to do so */ 
/*
CREATE VIEW TodosView AS
    SELECT TaskId, 
           Content,
           Completed, -- CheckBox: 1-checked, 0-unchecked
           SourceFileName,
           LocalFileName,
           DateTime(DatTimIns, 'unixepoch') AS DatTimIns, -- convert Integer(4) (treating it as Unix-Time)
           DateTime(DatTimUpd, 'unixepoch') AS DatTimUpd  -- to YYYY-MM-DD HH:MM:SS
      FROM Todos;
*/