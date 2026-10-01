variable "region" {
  type    = string
  default = "us-east-1"
}

variable "db_nombre" {
  type    = string
  default = "clipshare"
}

variable "db_usuario" {
  type    = string
  default = "clipshare_admin"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Se pasa con TF_VAR_db_password; nunca va escrita en el repositorio."
}

variable "cidr_autorizado" {
  type        = string
  description = "IP (formato x.x.x.x/32) que puede abrir la API en el puerto 8000."
  validation {
    condition     = can(cidrnetmask(var.cidr_autorizado)) && var.cidr_autorizado != "0.0.0.0/0"
    error_message = "Usa una IP concreta con /32, no 0.0.0.0/0."
  }
}

variable "entorno" {
  type        = string
  default     = "qa"
  description = "qa (Avance 2) o prod. Cada entorno usa su propio workspace de Terraform."
}
