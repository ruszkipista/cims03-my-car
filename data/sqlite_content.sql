INSERT INTO Todos (Content) VALUES ('One');                    -- activate the field Default
-- WAIT a few seconds --    
INSERT INTO Todos (Content) VALUES ('Two');                    -- same thing but with
INSERT INTO Todos (Content) VALUES ('Thr');                    --   later time values

UPDATE Todos SET Content = Content || ' Upd' WHERE TaskId = 1; -- activate the Update-trigger