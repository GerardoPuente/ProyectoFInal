terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "actual" {}

# QA conserva los nombres del Avance 2; cualquier otro entorno agrega su sufijo
locals {
  sufijo = var.entorno == "qa" ? "" : "-${var.entorno}"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }
}

# ---------------------------------------------------------------- S3
resource "aws_s3_bucket" "clips" {
  bucket        = "clipshare-${data.aws_caller_identity.actual.account_id}${local.sufijo}"
  force_destroy = true # entorno de laboratorio: permite destruir con clips dentro

  lifecycle {
    # El Learner Lab niega s3:GetBucketObjectLockConfiguration via SCP; el
    # provider intenta leerlo al "tocar" el recurso (incluye un recalculo de
    # tags_all sin cambios reales). Evita que ese recalculo dispare un apply
    # que falla por el permiso denegado.
    ignore_changes = [tags_all]
  }
}

resource "aws_s3_bucket_public_access_block" "clips" {
  bucket                  = aws_s3_bucket.clips.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Llave propia (CMK) para el bucket: rotacion automatica y politica de acceso controlada por nosotros
data "aws_iam_policy_document" "llave" {
  statement {
    sid       = "AdministracionDeLaCuenta"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.actual.account_id}:root"]
    }
  }
  statement {
    sid       = "UsoDesdeLaInstanciaDeLaApp"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.actual.account_id}:role/LabRole"]
    }
  }
}

resource "aws_kms_key" "clips" {
  description             = "Cifrado del bucket de clips de ClipShare (${var.entorno})"
  enable_key_rotation     = true
  deletion_window_in_days = 7
  policy                  = data.aws_iam_policy_document.llave.json
}

resource "aws_s3_bucket_server_side_encryption_configuration" "clips" {
  bucket = aws_s3_bucket.clips.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.clips.arn
    }
  }
}

resource "aws_s3_bucket_versioning" "clips" {
  bucket = aws_s3_bucket.clips.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Rechaza cualquier acceso que no use TLS
data "aws_iam_policy_document" "solo_tls" {
  statement {
    sid       = "DenegarSinTLS"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.clips.arn, "${aws_s3_bucket.clips.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "solo_tls" {
  bucket     = aws_s3_bucket.clips.id
  policy     = data.aws_iam_policy_document.solo_tls.json
  depends_on = [aws_s3_bucket_public_access_block.clips]
}

# ---------------------------------------------------------------- Red
resource "aws_security_group" "app" {
  name        = "clipshare-app${local.sufijo}"
  description = "Instancia de la app: HTTP solo desde la IP autorizada, sin SSH"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "API de ClipShare desde la IP autorizada"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.cidr_autorizado]
  }

  egress {
    description = "Salida HTTPS: S3, SSM, GitHub y PyPI"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Salida HTTP: los repositorios de Debian (apt) se descargan por el puerto 80"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Salida al RDS dentro de la VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }
}

resource "aws_security_group" "rds" {
  name        = "clipshare-rds${local.sufijo}"
  description = "RDS: solo acepta PostgreSQL desde la instancia de la app"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "PostgreSQL solo desde el grupo de la app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

# ---------------------------------------------------------------- RDS
resource "aws_db_subnet_group" "clipshare" {
  name       = "clipshare${local.sufijo}"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_db_instance" "clipshare" {
  identifier              = "clipshare-db${local.sufijo}"
  engine                  = "postgres"
  engine_version          = "15.14"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  storage_type            = "gp3"
  storage_encrypted       = true
  publicly_accessible     = false
  db_name                 = var.db_nombre
  username                = var.db_usuario
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.clipshare.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  backup_retention_period = 1
  skip_final_snapshot     = true # entorno de laboratorio
  deletion_protection     = false
  multi_az                = false
}

# ---------------------------------------------------------------- EC2
resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = "t3.small"
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = "LabInstanceProfile" # rol del Learner Lab: da acceso a S3 sin llaves
  user_data              = file("${path.module}/user_data.sh")

  metadata_options {
    http_tokens                 = "required" # IMDSv2
    http_put_response_hop_limit = 2          # los contenedores tambien alcanzan el rol
  }

  root_block_device {
    volume_size = 20
    encrypted   = true
  }

  tags = {
    Name = "clipshare-app${local.sufijo}"
  }
}
