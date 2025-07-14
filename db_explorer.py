import argparse
import sys
from tabulate import tabulate

def connect_to_db(db_type, host, port, user, password, database):
    """Connect to the specified database type."""
    if db_type.lower() == 'mysql':
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=host, port=port, user=user, password=password, database=database
            )
            return conn
        except ImportError:
            print("MySQL connector not installed. Run: pip install mysql-connector-python")
            sys.exit(1)
    elif db_type.lower() == 'postgresql':
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=host, port=port, user=user, password=password, dbname=database
            )
            return conn
        except ImportError:
            print("psycopg2 not installed. Run: pip install psycopg2-binary")
            sys.exit(1)
    else:
        print(f"Unsupported database type: {db_type}")
        sys.exit(1)

def list_tables(conn, db_type):
    """List all tables in the database."""
    cursor = conn.cursor()
    if db_type.lower() == 'mysql':
        cursor.execute("SHOW TABLES")
    else:  # postgresql
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
    tables = [table[0] for table in cursor.fetchall()]
    cursor.close()
    return tables

def describe_table(conn, db_type, table_name):
    """Show table structure."""
    cursor = conn.cursor()
    if db_type.lower() == 'mysql':
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        # For MySQL, the primary key info is in the 4th column (Key)
        primary_keys = [col[0] for col in columns if col[3] == 'PRI']
    else:  # postgresql
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
        """)
        columns = cursor.fetchall()
        # For PostgreSQL, we need a separate query to get primary keys
        cursor.execute(f"""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = '{table_name}'::regclass AND i.indisprimary
        """)
        primary_keys = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    return columns, primary_keys

def query_table(conn, table_name, limit=10):
    """Query data from a table with a limit."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
    rows = cursor.fetchall()
    
    # Get column names
    if cursor.description:
        columns = [desc[0] for desc in cursor.description]
    else:
        columns = []
    
    cursor.close()
    return columns, rows

def generate_er_diagram(conn, db_type, diagram_format):
    """Generate ER diagram in Mermaid or PlantUML format."""
    tables = list_tables(conn, db_type)
    
    if diagram_format == 'mermaid':
        # Mermaid is already wrapped in markdown code blocks
        diagram = "```mermaid\nerDiagram\n"
        
        # Define entities (tables)
        for table in tables:
            diagram += f"    {table} {{\n"
            columns, primary_keys = describe_table(conn, db_type, table)
            for column in columns:
                if db_type.lower() == 'mysql':
                    field, type_data = column[0], column[1]
                    # Clean up type data to avoid syntax issues
                    type_str = str(type_data)
                    if isinstance(type_data, bytes):
                        type_str = type_data.decode()
                    # Replace commas with underscore to avoid syntax errors
                    type_str = type_str.replace(',', '_')
                    # Highlight primary key with PK annotation
                    pk_marker = " PK" if field in primary_keys else ""
                    diagram += f"        {type_str} {field}{pk_marker}\n"
                else:  # postgresql
                    column_name, data_type = column[0], column[1]
                    # Clean up type data to avoid syntax issues
                    data_type = str(data_type).replace(',', '_')
                    # Highlight primary key with PK annotation
                    pk_marker = " PK" if column_name in primary_keys else ""
                    diagram += f"        {data_type} {column_name}{pk_marker}\n"
            diagram += "    }\n"
        
        # Add relationships
        cursor = conn.cursor()
        for table in tables:
            if db_type.lower() == 'mysql':
                # Get foreign keys for MySQL
                try:
                    cursor.execute(f"""
                        SELECT 
                            COLUMN_NAME, REFERENCED_TABLE_NAME
                        FROM
                            INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE
                            TABLE_NAME = '{table}'
                            AND REFERENCED_TABLE_NAME IS NOT NULL
                            AND CONSTRAINT_SCHEMA = DATABASE()
                    """)
                    foreign_keys = cursor.fetchall()
                    for fk in foreign_keys:
                        col_name, ref_table = fk
                        diagram += f"    {table} ||--o{{ {ref_table} : references\n"
                except Exception as e:
                    # Fallback to naming convention if query fails
                    columns = describe_table(conn, db_type, table)
                    for column in columns:
                        field = column[0]
                        if field.endswith('_id'):
                            ref_table = field[:-3]
                            if ref_table in tables:
                                diagram += f"    {table} ||--o{{ {ref_table} : references\n"
            else:  # postgresql
                # Get foreign keys for PostgreSQL
                try:
                    cursor.execute(f"""
                        SELECT
                            kcu.column_name,
                            ccu.table_name AS referenced_table
                        FROM
                            information_schema.table_constraints AS tc
                            JOIN information_schema.key_column_usage AS kcu
                              ON tc.constraint_name = kcu.constraint_name
                            JOIN information_schema.constraint_column_usage AS ccu
                              ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = '{table}'
                    """)
                    foreign_keys = cursor.fetchall()
                    for fk in foreign_keys:
                        col_name, ref_table = fk
                        diagram += f"    {table} ||--o{{ {ref_table} : references\n"
                except Exception as e:
                    # Fallback to naming convention if query fails
                    columns = describe_table(conn, db_type, table)
                    for column in columns:
                        column_name = column[0]
                        if column_name.endswith('_id'):
                            ref_table = column_name[:-3]
                            if ref_table in tables:
                                diagram += f"    {table} ||--o{{ {ref_table} : references\n"
        
        diagram += "```"
    else:  # plantuml
        # Wrap PlantUML in markdown code blocks
        diagram = "```plantuml\n@startuml\n"
        
        # Define entities (tables)
        for table in tables:
            diagram += f"entity {table} {{\n"
            columns, primary_keys = describe_table(conn, db_type, table)
            for column in columns:
                if db_type.lower() == 'mysql':
                    field, type_data = column[0], column[1]
                    # Clean up type data to avoid syntax issues
                    type_str = str(type_data)
                    if isinstance(type_data, bytes):
                        type_str = type_data.decode()
                    # Replace commas with underscore to avoid syntax errors
                    type_str = type_str.replace(',', '_')
                    # Highlight primary key with * prefix (PlantUML convention)
                    pk_marker = "*" if field in primary_keys else ""
                    diagram += f"  {pk_marker}{field} : {type_str}\n"
                else:  # postgresql
                    column_name, data_type = column[0], column[1]
                    # Clean up type data to avoid syntax issues
                    data_type = str(data_type).replace(',', '_')
                    # Highlight primary key with * prefix (PlantUML convention)
                    pk_marker = "*" if column_name in primary_keys else ""
                    diagram += f"  {pk_marker}{column_name} : {data_type}\n"
            diagram += "}\n"
        
        # Add relationships
        cursor = conn.cursor()
        for table in tables:
            if db_type.lower() == 'mysql':
                # Get foreign keys for MySQL
                try:
                    cursor.execute(f"""
                        SELECT 
                            COLUMN_NAME, REFERENCED_TABLE_NAME
                        FROM
                            INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE
                            TABLE_NAME = '{table}'
                            AND REFERENCED_TABLE_NAME IS NOT NULL
                            AND CONSTRAINT_SCHEMA = DATABASE()
                    """)
                    foreign_keys = cursor.fetchall()
                    for fk in foreign_keys:
                        col_name, ref_table = fk
                        diagram += f"{table} }}|--o| {ref_table} : references\n"
                except Exception as e:
                    # Fallback to naming convention if query fails
                    columns = describe_table(conn, db_type, table)
                    for column in columns:
                        field = column[0]
                        if field.endswith('_id'):
                            ref_table = field[:-3]
                            if ref_table in tables:
                                diagram += f"{table} }}|--o| {ref_table} : references\n"
            else:  # postgresql
                # Get foreign keys for PostgreSQL
                try:
                    cursor.execute(f"""
                        SELECT
                            kcu.column_name,
                            ccu.table_name AS referenced_table
                        FROM
                            information_schema.table_constraints AS tc
                            JOIN information_schema.key_column_usage AS kcu
                              ON tc.constraint_name = kcu.constraint_name
                            JOIN information_schema.constraint_column_usage AS ccu
                              ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = '{table}'
                    """)
                    foreign_keys = cursor.fetchall()
                    for fk in foreign_keys:
                        col_name, ref_table = fk
                        diagram += f"{table} }}|--o| {ref_table} : references\n"
                except Exception as e:
                    # Fallback to naming convention if query fails
                    columns = describe_table(conn, db_type, table)
                    for column in columns:
                        column_name = column[0]
                        if column_name.endswith('_id'):
                            ref_table = column_name[:-3]
                            if ref_table in tables:
                                diagram += f"{table} }}|--o| {ref_table} : references\n"
        
        diagram += "@enduml\n```"
    
    cursor.close()
    return diagram

def main():
    parser = argparse.ArgumentParser(description='Explore SQL databases')
    parser.add_argument('--type', required=True, choices=['mysql', 'postgresql'], 
                        help='Database type')
    parser.add_argument('--host', default='localhost', help='Database host')
    parser.add_argument('--port', type=int, help='Database port')
    parser.add_argument('--user', required=True, help='Database user')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--database', required=True, help='Database name')
    
    args = parser.parse_args()
    
    # Set default ports if not specified
    if not args.port:
        args.port = 3306 if args.type == 'mysql' else 5432
    
    # Connect to database
    conn = connect_to_db(args.type, args.host, args.port, args.user, 
                         args.password, args.database)
    
    while True:
        print("\nDatabase Explorer")
        print("1. List tables")
        print("2. Describe table")
        print("3. Query table")
        print("4. Generate ER Diagram")
        print("5. Exit")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            tables = list_tables(conn, args.type)
            print("\nTables in database:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table}")
        
        elif choice == '2':
            table_name = input("Enter table name: ")
            columns, primary_keys = describe_table(conn, args.type, table_name)
            print(f"\nStructure of table '{table_name}':")
            if args.type == 'mysql':
                headers = ["Field", "Type", "Null", "Key", "Default", "Extra"]
            else:
                headers = ["Column", "Data Type", "Nullable"]
            print(tabulate(columns, headers=headers))
            print(f"Primary keys: {', '.join(primary_keys)}")
        
        elif choice == '3':
            table_name = input("Enter table name: ")
            limit = input("Enter row limit (default 10): ") or 10
            try:
                column_names, rows = query_table(conn, table_name, int(limit))
                print(f"\nData from table '{table_name}':")
                print(tabulate(rows, headers=column_names))
            except Exception as e:
                print(f"Error querying table: {e}")
        
        elif choice == '4':
            print("\nChoose diagram format:")
            print("1. Mermaid")
            print("2. PlantUML")
            format_choice = input("Enter your choice (1/2): ")
            
            diagram_format = 'mermaid' if format_choice == '1' else 'plantuml'
            er_diagram = generate_er_diagram(conn, args.type, diagram_format)
            
            print(f"\n{diagram_format.capitalize()} ER Diagram:")
            print(er_diagram)
            
            # Optionally save to file
            save_option = input("Save diagram to file? (y/n): ")
            if save_option.lower() == 'y':
                extension = '.md' if diagram_format == 'mermaid' else '.puml'
                filename = input(f"Enter filename (default: er_diagram{extension}): ") or f"er_diagram{extension}"
                with open(filename, 'w') as f:
                    f.write(er_diagram)
                print(f"Diagram saved to {filename}")
        
        elif choice == '5':
            conn.close()
            print("Connection closed. Goodbye!")
            break
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
