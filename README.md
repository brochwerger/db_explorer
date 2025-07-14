# db_explorer

A command-line tool for exploring database structures and generating Entity-Relationship (ER) diagrams.

## Features

- Connect to MySQL and PostgreSQL databases
- List all tables in a database
- Describe table structure including columns and primary keys
- Query table data with customizable row limits
- Generate ER diagrams in multiple formats:
  - Mermaid markdown (with primary key highlighting)
  - PlantUML (with primary key highlighting)

## ER Diagram Features

Both diagram formats now support primary key highlighting:

- **Mermaid**: Primary keys are marked with `PK` annotation
- **PlantUML**: Primary keys are marked with `*` prefix

This makes it easy to identify primary keys in your generated diagrams at a glance.

## Usage

Run the tool with appropriate connection parameters:

```bash
python db_explorer.py --host localhost --user username --password password --database dbname --type mysql
```

Then follow the interactive menu to explore your database and generate diagrams.
