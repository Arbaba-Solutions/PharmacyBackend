# Supabase Migrations (Module 1)

This folder contains SQL migrations for Supabase/PostgreSQL.

## Applied in this module

- `migrations/20260406_001_initial_schema.sql`
  - Creates core enums and tables
  - Adds constraints and indexes
  - Adds helper functions and triggers
  - Enables and configures RLS policies by role
  - Creates private `prescriptions` storage bucket and object policies

## How to run

Use Supabase SQL Editor or Supabase CLI to run the migration file.

Example with SQL Editor:
1. Open your Supabase project.
2. Go to SQL Editor.
3. Paste the migration content.
4. Run and verify table creation.

## Notes

- Authentication is expected through Supabase Auth (`auth.users`).
- Profile and domain data live in `public` schema.
- Long-term source of truth for data modeling will be Django models in Module 2+.
