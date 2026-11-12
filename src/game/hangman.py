import unicodedata
import re

class Hangman:
    def __init__(self, palavra: str, vidas: int = 6):
        self.palavra = self.normaliza_palavra(palavra)
        self.vidas = vidas
        self.letras_tentadas: set[str] = set()
        self.letras_erradas: list[str] = []
        self.estado = "RUNNING"

    @staticmethod
    def normaliza_palavra(palavra: str) -> str:

        #remove os espaços em branco e padroniza em minuscula
        palavra = palavra.strip().lower()

        #separa os acentos
        palavra_nfkd = unicodedata.normalize("NFKD", palavra)

        #remove os acentos
        palavra_normalizada = "".join([caractere for caractere in palavra_nfkd if not unicodedata.combining(caractere)])

        if len(palavra_normalizada) >= 3 and len(palavra_normalizada)<= 20:
            if bool(re.fullmatch(r"[a-z]+", palavra_normalizada)):
                return palavra_normalizada


        raise ValueError("Palavra inválida!")

    
    def palpite(self, letra: str) -> bool:

        if self.estado != "RUNNING":
            return False
        
        letra = letra.lower().strip()

        if not re.fullmatch(r"[a-z]", letra):
            return False
        
        if letra in self.letras_tentadas:
            return False
        
        self.letras_tentadas.add(letra)

        if letra in self.palavra:
            self.verifica_estado()
            return True
        
        self.letras_erradas.append(letra)
        self.vidas = max(0, self.vidas - 1)
        self.verifica_estado()
        return False
        

    def mascara(self) -> str:
        mascara = ""
        for letra in self.palavra:
            if letra in self.letras_tentadas:
                mascara += letra
            else:
                mascara += "_"

        return mascara

    def tentar_palavra(self, palpite_palavra: str) -> bool:
        if self.estado != "RUNNING":
            return False
        palpite_palavra = self.normaliza_palavra(palpite_palavra)

        if palpite_palavra == self.palavra:
            self.estado = "WON"
            return True

        self.vidas = max(0, self.vidas - 1)
        self.verifica_estado()
        return False

    def verifica_estado(self) -> str:
        if self.mascara() == self.palavra:
            self.estado = "WON"

        elif self.vidas <= 0:
            self.estado = "LOST"

        return self.estado

    def snapshot(self) -> dict:
        return{
            "masked": self.mascara(),
            "wrong_letters": self.letras_erradas.copy(),
            "lives": self.vidas,
            "status": self.estado,          
        }
            
        


    