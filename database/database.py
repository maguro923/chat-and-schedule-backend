from psycopg import sql
from psycopg_pool import ConnectionPool
from typing import Optional, List, Dict

class Database:
    def __init__(self):
        try:
            # 接続プールの作成
            self.pool = ConnectionPool(
                "host=192.168.0.151 dbname=chatandschedule user=postgres password=maguro39",
                min_size=1,
                max_size=10
            )
            print('\033[32m' + "DBinfo" + '\033[0m' + ":   " + "Database connection pool created successfully")
        except Exception as e:
            print(f"Error creating connection pool: {e}")
            self.pool = None

    def get_connection(self):
        """接続プールから接続を取得"""
        try:
            conn = self.pool.connection()
            conn.autocommit = False
            return conn
        except Exception as e:
            print(f"Error getting connection: {e}")
            raise e

    def fetch_all_data(self, cursor, table: str) -> Optional[List[Dict]]:
        try:
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
            cursor.execute(query)
            return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching all data: {e}")
            raise e

    def fetch(self, cursor, table: str, filters: dict) -> Optional[List[Dict]]:
        try:
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
            raise e
        
    def fetch_before_datetime(self, cursor, table:str, filters: dict, datetime_column: str, datetime: str) -> Optional[List[Dict]]:
        try:
            filter_clauses = []
            values = []
            for key, value in filters.items():
                filter_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                values.append(value)
            values.append(datetime)
            query = sql.SQL("SELECT * FROM {} WHERE {} AND {} <= %s").format(
                sql.Identifier(table),
                sql.SQL(" AND ").join(filter_clauses),
                sql.Identifier(datetime_column)
            )
            cursor.execute(query, values)
            return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching data: {e}")
            raise e
    
    def fetch_after_datetime(self, cursor, table:str, filters: dict, datetime_column: str, datetime: str) -> Optional[List[Dict]]:
        try:
            filter_clauses = []
            values = []
            for key, value in filters.items():
                filter_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                values.append(value)
            values.append(datetime)
            query = sql.SQL("SELECT * FROM {} WHERE {} AND {} > %s").format(
                sql.Identifier(table),
                sql.SQL(" AND ").join(filter_clauses),
                sql.Identifier(datetime_column)
            )
            cursor.execute(query, values)
            return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching data: {e}")
            raise e
    
    def insert(self, cursor, table: str, data: dict) -> bool:
        try:
            keys = data.keys()
            values = list(data.values())
            query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table),
                sql.SQL(", ").join(map(sql.Identifier, keys)),
                sql.SQL(", ").join(sql.Placeholder() * len(keys))
            )
            cursor.execute(query, values)
            return True
        except Exception as e:
            print(f"Error inserting data: {e}")
            return False

    def update(self, cursor, table: str, data: dict, filters: dict) -> bool:
        try:
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
            cursor.execute(query, values)
            return True
        except Exception as e:
            print(f"Error updating data: {e}")
            return False

    def delete(self, cursor, table: str, filters: dict) -> bool:
        try:
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
            return True
        except Exception as e:
            print(f"Error deleting data: {e}")
            return False
        

    def like(self, cursor, table: str, filters: dict, like_filteers: dict) -> Optional[List[Dict]]:
        try:
            filter_clauses = []
            values = []
            for key, value in filters.items():
                filter_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                values.append(value)
            for key, value in like_filteers.items():
                filter_clauses.append(sql.SQL("{} LIKE %s").format(sql.Identifier(key)))
                values.append(f'%{value}%')
            query = sql.SQL("SELECT * FROM {} WHERE {}").format(
                sql.Identifier(table),
                sql.SQL(" AND ").join(filter_clauses)
            )
            cursor.execute(query, values)
            return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching data: {e}")
            raise e

database = Database()

# example
"""
from psycopg.rows import dict_row
with database.get_connection() as conn:
    with conn.cursor(row_factory=dict_row) as cursor:
        a = database.fetch(cursor, "users", {"name": "test"})
"""