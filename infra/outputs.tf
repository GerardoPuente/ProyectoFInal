output "bucket" {
  value = aws_s3_bucket.clips.bucket
}

output "db_host" {
  value = aws_db_instance.clipshare.address
}

output "instancia_id" {
  value = aws_instance.app.id
}

output "ip_publica" {
  value = aws_instance.app.public_ip
}
