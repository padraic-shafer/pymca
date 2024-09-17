import enable_pymca_import  # noqa: F401

from unittest.mock import Mock, patch

import pytest
from pytestqt.qtbot import QtBot

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication

from PyMca5.PyMcaGui.io.TiledCatalogSelector import TiledCatalogSelector
from PyMca5.PyMcaGui.io.QTiledCatalogSelectorDialog import QTiledCatalogSelectorDialog


@pytest.fixture
def dialog_model(qapp: QApplication):
    model = TiledCatalogSelector(parent=qapp)
    yield model


def test_init(qtbot: QtBot, dialog_model: TiledCatalogSelector):
    """Can create a QTiledCatalogSelectorDialog object."""
    QTiledCatalogSelectorDialog(model=dialog_model)


def test_render(qtbot: QtBot, dialog_model: TiledCatalogSelector):
    """Can render a QTiledCatalogSelectorDialog window."""
    dialog = QTiledCatalogSelectorDialog(model=dialog_model)
    dialog.show()
    qtbot.addWidget(dialog)

# Functional tests...

def test_connection(qtbot: QtBot, dialog_model: TiledCatalogSelector):
    """Verify changes enacted by initiating a connection."""
    model = dialog_model
    expected_url = "New URL"

    model.url = expected_url
    dialog = QTiledCatalogSelectorDialog(model=model)
    dialog.show()
    qtbot.addWidget(dialog)

    with patch.object(model, "client_from_url") as mock_client_constructor:
        client = Mock()
        client.uri = model.url
        client.context.api_uri = ""
        mock_client_constructor.return_value = client

        dialog.connect_button.click()
    
    assert expected_url in dialog.connection_label.text()


def test_url_editing(qtbot: QtBot, dialog_model: TiledCatalogSelector):
    """Verify changes enacted by interacting with the url_entry widget."""
    dialog = QTiledCatalogSelectorDialog(model=dialog_model)
    dialog.show()
    qtbot.addWidget(dialog)

    # Default text shown
    assert dialog.url_entry.placeholderText() == "Enter a url"

    # Disply the URL when it is initialized in the model
    dialog_model.url = "Initial url"
    dialog.reset_url_entry()
    assert dialog.url_entry.displayText() == "Initial url"

    # Simulate editing the url_entry text
    dialog.url_entry.textEdited.emit("New url")
    dialog.url_entry.editingFinished.emit()
    assert dialog.model.url == "New url"


def test_url_edit_focus(
    qapp: QApplication,
    qtbot: QtBot,
    dialog_model: TiledCatalogSelector,
):
    """Verify custom event filtering for url_entry widget."""
    dialog = QTiledCatalogSelectorDialog(model=dialog_model)
    dialog.show()
    qtbot.addWidget(dialog)

    dialog_model._url_buffer = "Some text"
    qapp.sendEvent(dialog.url_entry, QEvent(QEvent.Type.FocusIn))
    assert dialog_model._url_buffer is None