import psycopg
from psycopg import sql
import psycopg.rows

class Database:
    def __init__(self):
        try:
            with self.get_connection() as connection:
                with connection.cursor() as cursor:
                    print('\033[32m'+"DBinfo"+'\033[0m'+":   "+"Database connection successful")
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            self.connection = None

    @staticmethod
    def get_connection():
        return psycopg.connect(
            host="192.168.0.151",
            dbname="chatandschedule",
            user="postgres",
            password="maguro39"
        )

    def fetch_all_data(self, table: str):
        try:
            with self.get_connection() as connection:
                with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
                    cursor.execute(query)
                    return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching all data: {e}")
            return None

    def fetch(self, table: str, filters: dict):
        try:
            with self.get_connection() as connection:
                with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                    filter_clauses = []
                    values = []
                    for key, value in filters.items():
                        filter_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                        values.append(value)
                    query = sql.SQL("SELECT * FROM {} WHERE {}").format(
                        sql.Identifier(table),
                        sql.SQL(" AND ").join(filter_clauses)
                    )
                    cursor.execute(query, values)
                    return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

    def insert(self, table: str, data: dict):
        try:
            with self.get_connection() as connection:
                with connection.cursor() as cursor:
                    keys = data.keys()
                    values = list(data.values())
                    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(map(sql.Identifier, keys)),
                        sql.SQL(", ").join(sql.Placeholder() * len(keys))
                    )
                    cursor.execute(query, values)
                    connection.commit()
                    return True
        except Exception as e:
            print(f"Error inserting data: {e}")
            return False

    def update(self, table: str, data: dict, filters: dict):
        try:
            with self.get_connection() as connection:
                with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                    set_clauses = []
                    filter_clauses = []
                    values = []
                    for key, value in data.items():
                        set_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                        values.append(value)
                    for key, value in filters.items():
                        filter_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                        values.append(value)
                    query = sql.SQL("UPDATE {} SET {} WHERE {}").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(set_clauses),
                        sql.SQL(" AND ").join(filter_clauses)
                    )
                    #print(query)
                    #print(values)
                    cursor.execute(query, values)
                    connection.commit()
                    return True
        except Exception as e:
            print(f"Error updating data: {e}")
            return False

    def delete(self, table: str, filters: dict):
        try:
            with self.get_connection() as connection:
                with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                    filter_clauses = []
                    values = []
                    for key, value in filters.items():
                        filter_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                        values.append(value)
                    query = sql.SQL("DELETE FROM {} WHERE {}").format(
                        sql.Identifier(table),
                        sql.SQL(" AND ").join(filter_clauses)
                    )
                    cursor.execute(query, values)
                    connection.commit()
                    return True
        except Exception as e:
            print(f"Error deleting data: {e}")
            return False

database = Database()