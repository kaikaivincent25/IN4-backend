from app.db.session import Base


def test_core_metadata_tables_are_registered() -> None:
    table_names = {table.name for table in Base.metadata.tables.values()}

    expected = {
        "users_customuser",
        "categories_category",
        "categories_categorytemplate",
        "experts_expert",
        "articles_article",
        "articles_articledraft",
        "engagements_savedarticle",
        "engagements_readhistory",
        "engagements_articlestats",
    }

    assert expected.issubset(table_names)
