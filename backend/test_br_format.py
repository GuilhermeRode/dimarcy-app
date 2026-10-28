"""CPF/CNPJ/phone formatting and IE extraction self-check. Run from backend/:  python test_br_format.py"""
from app.br_format import extract_state_registration as ie, format_document as doc, format_phone as phone

assert doc("12345678000190") == "12.345.678/0001-90"
assert doc("12.345.678/0001-90") == "12.345.678/0001-90"
assert doc("12345678901") == "123.456.789-01"
assert doc(" 123 ") == "123"  # incomplete: kept as typed
assert doc(None) is None

assert phone("47999998888") == "(47) 99999-8888"
assert phone("4733334444") == "(47) 3333-4444"
assert phone("+55 47 99999-8888") == "(47) 99999-8888"
assert phone("047 3333-4444") == "(47) 3333-4444"
assert phone("ramal 12") == "ramal 12"
assert phone("4799735351") == "(47) 99973-5351"  # old 8-digit mobile gets the 9
assert phone("(047) 99735-3510") == "(47) 99735-3510"
assert phone("0xx47 3333-4444") == "(47) 3333-4444"
assert phone("+55 (47) 9973-5351") == "(47) 99973-5351"

assert ie("IE: 254.123.456") == ("254.123.456", None)
assert ie("I.E. 123456789 - entregar pela manhã") == ("123456789", "entregar pela manhã")
assert ie("Entregar à tarde\nInscrição Estadual: 10.123.456-7\nPagamento em boleto") == \
    ("10.123.456-7", "Entregar à tarde\nPagamento em boleto")
assert ie("insc. est. nº 123/4567890") == ("123/4567890", None)
assert ie("IE isento") == ("ISENTO", None)
assert ie("Inscrição estadual: 256422974") == ("256422974", None)  # how the real notes have it
assert ie("Cliente antigo, paga em dia") == (None, "Cliente antigo, paga em dia")
assert ie("CLIENTE 123") == (None, "CLIENTE 123")  # "IE" inside a word is not a registration
assert ie(None) == (None, None)
from app.br_format import format_state_registration as fie  # noqa: E402

assert fie("254123456", "SC") == "254.123.456"
assert fie("110042490114", "sp") == "110.042.490.114"
assert fie("0240000011", "RS") == "024/0000011"
assert fie("12345678", "BA") == "123456-78" and fie("123456789", "BA") == "1234567-89"
assert fie("254.123.456", "SC") == "254.123.456"  # already formatted
assert fie("12345", "SC") == "12345"  # wrong length: kept
assert fie("254123456", None) == "254123456"  # no UF: kept
assert fie("isento", "SC") == "ISENTO"
print("ok")
