"""Add supplier_id and created/updated dates

Revision ID: c8bce0740af
Revises: 4cb7869866dc
Create Date: 2015-01-26 15:23:03.984803

"""

# revision identifiers, used by Alembic.
revision = 'c8bce0740af'
down_revision = '4cb7869866dc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('services', sa.Column('created_at', sa.DateTime(), nullable=False))
    op.add_column('services', sa.Column('supplier_id', sa.BigInteger(), nullable=False))
    op.add_column('services', sa.Column('updated_at', sa.DateTime(), nullable=False))
    op.create_index(op.f('ix_services_supplier_id'), 'services', ['supplier_id'], unique=False)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_services_supplier_id'), table_name='services')
    op.drop_column('services', 'updated_at')
    op.drop_column('services', 'supplier_id')
    op.drop_column('services', 'created_at')
    ### end Alembic commands ###